"""크롤 상태를 점검해 이상이면 알림을 보낸다 (감시 계층 2 — 서버 내부).

외부 감시(GitHub Actions cron)는 서버가 완전히 죽어도 잡지만 하루 1회라 최대
24시간 지연된다. 이 계층은 크롤이 끝난 직후 스스로 점검해 즉시 알린다.
12일 사고 때 백엔드는 살아 있었으므로, 이 계층이 있었다면 첫날 알림이 왔다.

알림 피로 방지 (docs/MONITORING_PLAN.md 7절)
- 같은 장애가 이어지는 동안은 처음 1회만 보낸다 (지문 + 억제 시간)
- ok로 돌아오면 회복 알림을 1회 보낸다
- 알림 발송이 실패해도 호출한 배치는 계속 돌아야 하므로 예외를 삼킨다
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.notify import send_webhook
from app.core.time import as_utc, utc_now
from app.db.models.monitor import MonitorState
from app.services.crawler_monitor import OK, evaluate_crawler_health

logger = logging.getLogger(__name__)

STATE_KEY = "crawler_health"

_ICON = {"down": "🔴", "warn": "🟠"}


async def check_and_notify(db: AsyncSession, *, trigger: str) -> str:
    """크롤 상태를 판정하고 필요하면 알린다. 판정된 상태를 돌려준다.

    trigger는 알림 본문에 남기는 호출 맥락이다 ("크롤 종료 직후" 등).
    """
    try:
        health = await evaluate_crawler_health(db)
    except Exception as e:
        logger.error("크롤 상태 판정 실패: %s", e)
        return "unknown"

    state = (
        await db.execute(select(MonitorState).where(MonitorState.key == STATE_KEY))
    ).scalar_one_or_none()

    if health.is_ok:
        # 직전에 장애를 알렸다면 회복을 알린다
        if state is not None and state.status != OK:
            await _notify(health, trigger=trigger, recovered=True)
        await _remember(db, state, health)
        logger.info("[감시] 크롤 정상 (%s)", trigger)
        return health.status

    fingerprint = health.fingerprint()
    if state is not None and state.status != OK and state.fingerprint == fingerprint:
        age_hours = (utc_now() - as_utc(state.notified_at)).total_seconds() / 3600
        if age_hours < settings.ALERT_SUPPRESS_HOURS:
            logger.info(
                "[감시] 같은 장애 알림 억제 — %.1f시간 전 발송 (기준 %d시간)",
                age_hours,
                settings.ALERT_SUPPRESS_HOURS,
            )
            return health.status

    await _notify(health, trigger=trigger, recovered=False)
    await _remember(db, state, health)
    return health.status


async def _notify(health, *, trigger: str, recovered: bool) -> None:
    if recovered:
        header = "🟢 크롤이 정상으로 회복됐습니다"
    else:
        header = f"{_ICON.get(health.status, '🔴')} 크롤 이상 감지 ({health.status})"

    body = "\n".join(
        [
            header,
            f"점검 시점: {trigger}",
            "```",
            *health.summary_lines(),
            "```",
            "상세는 서버 로그를 확인해주세요.",
        ]
    )
    sent = await send_webhook(body)
    logger.warning("[감시] 알림 %s — status=%s trigger=%s", "발송" if sent else "미발송", health.status, trigger)


async def _remember(db: AsyncSession, state: MonitorState | None, health) -> None:
    """마지막으로 알린 상태를 기록한다. 실패해도 배치를 막지 않는다."""
    try:
        if state is None:
            db.add(
                MonitorState(
                    key=STATE_KEY,
                    status=health.status,
                    fingerprint=health.fingerprint(),
                    notified_at=utc_now(),
                )
            )
        else:
            state.status = health.status
            state.fingerprint = health.fingerprint()
            state.notified_at = utc_now()
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("감시 상태 기록 실패: %s", e)
