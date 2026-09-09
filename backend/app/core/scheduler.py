import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings

logger = logging.getLogger(__name__)
# 스케줄은 UTC로 고정한다. 원래 scheduler에 Asia/Seoul을 주고 CronTrigger는
# 타임존 없이 만들었는데, 스케줄러 밖에서 만든 트리거는 **컨테이너 로컬 타임존**을
# 쓴다. 백엔드 컨테이너에 TZ가 없어(UTC) 결과적으로 UTC로 돌고 있었고, 코드와
# 동작이 어긋난 상태였다. 누가 TZ를 설정하면 전 스케줄이 9시간 밀린다.
# 현재 동작(UTC)을 그대로 유지하면서 명시적으로 못박는다.
scheduler = AsyncIOScheduler(timezone=timezone.utc)


def _cron(spec: str) -> CronTrigger:
    """"분 시 일 월 요일" 문자열 → UTC 고정 CronTrigger."""
    minute, hour, day, month, day_of_week = spec.split()
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone=timezone.utc,
    )


async def _run_all_crawlers() -> None:
    from app.crawlers.base import run_all_crawlers
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            await run_all_crawlers(db)
        except Exception as e:
            logger.error("크롤러 실행 중 오류: %s", e)


async def _run_alert_check() -> None:
    from app.services.alert import process_watchlist_alerts
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            created = await process_watchlist_alerts(db)
            logger.info("알림 체크 완료 — %d개 생성", created)
        except Exception as e:
            logger.error("알림 체크 중 오류: %s", e)


async def _run_crawler_monitor() -> None:
    """크롤이 아예 시작조차 못 한 경우를 잡는 일일 재점검.

    정상 경로에서는 크롤 종료 직후 run_all_crawlers가 스스로 점검하므로 여기서
    다시 볼 필요가 없다. 하지만 배치가 발화조차 못 하면 그 점검도 안 돌아간다.
    """
    from app.db.session import AsyncSessionLocal
    from app.services.crawler_alert import check_and_notify

    async with AsyncSessionLocal() as db:
        try:
            await check_and_notify(db, trigger="일일 재점검")
        except Exception as e:
            logger.error("크롤 감시 중 오류: %s", e)


def setup_scheduler() -> None:
    scheduler.add_job(
        _run_all_crawlers,
        _cron(settings.CRAWLER_SCHEDULE),
        id="crawl_all",
        name="전체 크롤링",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_alert_check,
        _cron(settings.ALERT_SCHEDULE),
        id="alert_check",
        name="가격 알림 체크",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_crawler_monitor,
        _cron(settings.MONITOR_SCHEDULE),
        id="crawler_monitor",
        name="크롤 감시",
        replace_existing=True,
    )


def get_job_info() -> list[dict]:
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        trigger = str(job.trigger)
        cron_str = trigger if "cron" in trigger.lower() else "—"
        jobs.append({
            "job_id": job.id,
            "name": job.name,
            "cron": cron_str,
            "next_run_at": next_run,
            "status": "active" if next_run else "paused",
        })
    return jobs
