import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


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


def setup_scheduler() -> None:
    crawler_parts = settings.CRAWLER_SCHEDULE.split()
    alert_parts = settings.ALERT_SCHEDULE.split()

    scheduler.add_job(
        _run_all_crawlers,
        CronTrigger(
            minute=crawler_parts[0],
            hour=crawler_parts[1],
            day=crawler_parts[2],
            month=crawler_parts[3],
            day_of_week=crawler_parts[4],
        ),
        id="crawl_all",
        name="전체 크롤링",
        replace_existing=True,
        max_instances=1,  # 이전 크롤링이 안 끝났으면 이번 회차 스킵 (동시 실행 방지)
        coalesce=True,  # 밀린 실행이 여러 개면 1회로 합침
        misfire_grace_time=3600,  # 정각을 놓쳐도 1시간 내면 실행
    )
    scheduler.add_job(
        _run_alert_check,
        CronTrigger(
            minute=alert_parts[0],
            hour=alert_parts[1],
            day=alert_parts[2],
            month=alert_parts[3],
            day_of_week=alert_parts[4],
        ),
        id="alert_check",
        name="가격 알림 체크",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
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
