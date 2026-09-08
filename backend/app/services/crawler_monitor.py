"""크롤 상태 판정 — 감시 엔드포인트와 알림 잡이 같은 로직을 쓴다.

판정이 두 곳에 복사되면 반드시 어긋나므로 여기 한 곳에만 둔다.
- GET /api/v1/health/crawlers (외부 감시가 찌른다)
- 스케줄러의 자기점검 잡 (크롤 종료 직후 + 매일 재점검)

"로그에 실패가 있나"가 아니라 "마지막 성공이 얼마나 오래됐나"로 판정한다.
8/25~9/5 12일간 크롤이 한 번도 성공하지 못했는데 crawler_log에 fail 행조차
남지 않아 아무도 몰랐다 — 배치의 첫 DB 작업인 로그 insert 자체가 죽었기 때문이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

PLATFORMS = ("daangn", "bunjang", "joongna")

OK = "ok"
WARN = "warn"
DOWN = "down"

_SEVERITY = {OK: 0, WARN: 1, DOWN: 2}


@dataclass
class PlatformHealth:
    platform: str
    state: str
    last_success_age_hours: float | None
    last_status: str | None
    last_items_upserted: int | None
    running_age_hours: float | None
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "state": self.state,
            "last_success_age_hours": self.last_success_age_hours,
            "last_status": self.last_status,
            "last_items_upserted": self.last_items_upserted,
            "running_age_hours": self.running_age_hours,
            "reasons": self.reasons,
        }


@dataclass
class CrawlerHealth:
    status: str
    platforms: list[PlatformHealth]
    stale_threshold_hours: int

    @property
    def is_ok(self) -> bool:
        return self.status == OK

    def fingerprint(self) -> str:
        """같은 장애가 이어지는 동안 중복 알림을 억제하기 위한 키.

        플랫폼별 상태만 담는다 — 경과 시간은 매 점검마다 달라지므로 넣으면
        억제가 동작하지 않는다.
        """
        return ";".join(f"{p.platform}={p.state}" for p in self.platforms)

    def summary_lines(self) -> list[str]:
        """알림에 넣을 요약. 에러 원문은 넣지 않는다(내부 정보 노출 방지)."""
        lines = []
        for p in self.platforms:
            age = "기록 없음" if p.last_success_age_hours is None else f"{p.last_success_age_hours}h 전"
            detail = "; ".join(p.reasons) if p.reasons else f"신규 {p.last_items_upserted or 0}건"
            lines.append(f"{p.platform:8} {p.state:5} 마지막 성공 {age} — {detail}")
        return lines

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "stale_threshold_hours": self.stale_threshold_hours,
            "platforms": [p.to_dict() for p in self.platforms],
        }


_AGE_SQL = text(
    """
    SELECT platform,
           MIN(CASE WHEN status = 'success' THEN
               TIMESTAMPDIFF(SECOND, COALESCE(finished_at, started_at), UTC_TIMESTAMP())
           END) AS success_age_sec,
           MAX(CASE WHEN status = 'running' THEN
               TIMESTAMPDIFF(SECOND, started_at, UTC_TIMESTAMP())
           END) AS running_age_sec
    FROM crawler_log
    GROUP BY platform
    """
)

_LAST_SQL = text(
    """
    SELECT c.platform, c.status, c.items_upserted
    FROM crawler_log c
    JOIN (SELECT platform, MAX(log_id) AS log_id FROM crawler_log GROUP BY platform) m
      ON m.platform = c.platform AND m.log_id = c.log_id
    """
)


async def evaluate_crawler_health(db: AsyncSession) -> CrawlerHealth:
    """플랫폼별로 판정하고 최악을 전체 상태로 삼는다.

    경과 시간은 SQL의 UTC_TIMESTAMP()로 계산한다. started_at·finished_at은
    애플리케이션이 UTC로 쓰지만, 세션 타임존 설정에 좌우되지 않게 하기 위함이다.
    """
    stale_seconds = settings.CRAWLER_STALE_HOURS * 3600
    running_seconds = settings.CRAWLER_RUNNING_MAX_HOURS * 3600

    ages = {r.platform: r for r in (await db.execute(_AGE_SQL)).all()}
    lasts = {r.platform: r for r in (await db.execute(_LAST_SQL)).all()}

    results: list[PlatformHealth] = []
    worst = OK
    for platform in PLATFORMS:
        age_row = ages.get(platform)
        last = lasts.get(platform)
        age = int(age_row.success_age_sec) if age_row and age_row.success_age_sec is not None else None
        running_age = (
            int(age_row.running_age_sec) if age_row and age_row.running_age_sec is not None else None
        )

        reasons: list[str] = []
        state = OK
        if age is None:
            state = DOWN
            reasons.append("성공 기록 없음")
        elif age > stale_seconds:
            state = DOWN
            reasons.append(
                f"마지막 성공이 {age // 3600}시간 전 (기준 {settings.CRAWLER_STALE_HOURS}시간)"
            )
        if last is not None and last.status == "fail":
            reasons.append("마지막 시도 실패")
            state = DOWN if state == DOWN else WARN
        if running_age is not None and running_age > running_seconds:
            reasons.append(f"running 상태로 {running_age // 3600}시간 잔류")
            state = DOWN if state == DOWN else WARN
        if state == OK and last is not None and last.status == "success" and not last.items_upserted:
            reasons.append("마지막 성공의 신규 수집량이 0")
            state = WARN

        results.append(
            PlatformHealth(
                platform=platform,
                state=state,
                last_success_age_hours=round(age / 3600, 1) if age is not None else None,
                last_status=last.status if last else None,
                last_items_upserted=int(last.items_upserted) if last else None,
                running_age_hours=round(running_age / 3600, 1) if running_age is not None else None,
                reasons=reasons,
            )
        )
        if _SEVERITY[state] > _SEVERITY[worst]:
            worst = state

    return CrawlerHealth(
        status=worst,
        platforms=results,
        stale_threshold_hours=settings.CRAWLER_STALE_HOURS,
    )
