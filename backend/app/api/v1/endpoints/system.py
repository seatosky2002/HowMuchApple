from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["System"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    from app.core.scheduler import scheduler
    scheduler_status = "ok" if scheduler.running else "error"

    overall = "ok" if db_status == "ok" and scheduler_status == "ok" else "degraded"

    response = {
        "status": overall,
        "db": db_status,
        "scheduler": scheduler_status,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=response,
        status_code=200 if overall == "ok" else 503,
    )


PLATFORMS = ("daangn", "bunjang", "joongna")


@router.get("/health/crawlers")
async def crawler_health(db: AsyncSession = Depends(get_db)):
    """크롤 신선도를 인증 없이 판정한다 — 외부 감시(GitHub Actions cron)용.

    /health는 db·scheduler만 보고 크롤이 며칠 멈춰도 ok를 반환한다. 실제로
    8/25~9/5 12일간 크롤이 한 번도 성공하지 못했는데 아무도 알지 못했다.
    crawler_log에 fail 행조차 남지 않는 실패 경로가 있어서, 로그 유무가 아니라
    "마지막 성공이 얼마나 오래됐나"로 판정해야 한다.

    상태가 ok가 아니면 503을 반환하므로 감시 쪽은 `curl -f` 한 줄로 끝난다.

    판정 (플랫폼별로 본 뒤 최악을 전체 상태로 삼는다)
      down — 마지막 성공이 CRAWLER_STALE_HOURS를 넘었거나 성공 기록이 아예 없음
      warn — 마지막 시도가 실패했거나 / running이 CRAWLER_RUNNING_MAX_HOURS 이상
             잔류 / 마지막 성공의 수집량이 0
      ok   — 그 외

    경과 시간은 SQL의 UTC_TIMESTAMP()로 계산한다. started_at·finished_at은
    애플리케이션이 UTC로 쓰지만 세션 타임존 설정에 좌우되지 않게 하기 위함이다.
    """
    stale_seconds = settings.CRAWLER_STALE_HOURS * 3600
    running_seconds = settings.CRAWLER_RUNNING_MAX_HOURS * 3600

    rows = (
        await db.execute(
            text(
                """
                SELECT platform,
                       MAX(CASE WHEN status = 'success' THEN
                           TIMESTAMPDIFF(SECOND, COALESCE(finished_at, started_at), UTC_TIMESTAMP())
                       END) IS NOT NULL AS has_success,
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
        )
    ).all()
    by_platform = {r.platform: r for r in rows}

    # 플랫폼별 마지막 시도의 상태·수집량 (성공 여부와 무관하게 가장 최근 것)
    last_rows = (
        await db.execute(
            text(
                """
                SELECT c.platform, c.status, c.items_upserted, c.error
                FROM crawler_log c
                JOIN (SELECT platform, MAX(log_id) AS log_id FROM crawler_log GROUP BY platform) m
                  ON m.platform = c.platform AND m.log_id = c.log_id
                """
            )
        )
    ).all()
    last_by_platform = {r.platform: r for r in last_rows}

    platforms = []
    worst = "ok"
    for platform in PLATFORMS:
        row = by_platform.get(platform)
        last = last_by_platform.get(platform)
        age = int(row.success_age_sec) if row and row.success_age_sec is not None else None
        running_age = int(row.running_age_sec) if row and row.running_age_sec is not None else None

        reasons = []
        state = "ok"
        if age is None:
            state, _ = "down", reasons.append("성공 기록 없음")
        elif age > stale_seconds:
            state, _ = "down", reasons.append(
                f"마지막 성공이 {age // 3600}시간 전 (기준 {settings.CRAWLER_STALE_HOURS}시간)"
            )
        if last is not None and last.status == "fail":
            reasons.append(f"마지막 시도 실패: {(last.error or '')[:120]}")
            state = "down" if state == "down" else "warn"
        if running_age is not None and running_age > running_seconds:
            reasons.append(f"running 상태로 {running_age // 3600}시간 잔류")
            state = "down" if state == "down" else "warn"
        if state == "ok" and last is not None and last.status == "success" and not last.items_upserted:
            reasons.append("마지막 성공의 신규 수집량이 0")
            state = "warn"

        platforms.append({
            "platform": platform,
            "state": state,
            "last_success_age_hours": round(age / 3600, 1) if age is not None else None,
            "last_status": last.status if last else None,
            "last_items_upserted": int(last.items_upserted) if last else None,
            "running_age_hours": round(running_age / 3600, 1) if running_age is not None else None,
            "reasons": reasons,
        })
        if state == "down" or (state == "warn" and worst == "ok"):
            worst = state

    from fastapi.responses import JSONResponse

    return JSONResponse(
        content={
            "status": worst,
            "stale_threshold_hours": settings.CRAWLER_STALE_HOURS,
            "platforms": platforms,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
        status_code=200 if worst == "ok" else 503,
    )
