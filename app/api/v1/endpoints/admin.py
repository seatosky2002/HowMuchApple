from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.core.exceptions import BadRequest, NotFound
from app.db.models.alert import Alert, Watchlist
from app.db.models.crawler import CrawlerLog
from app.db.models.item import Item
from app.db.models.sku import SKU
from app.db.models.user import User, UserStatus
from app.db.session import get_db
from app.schemas.admin import (
    AdminStatsResponse,
    AdminUserItem,
    AdminUsersResponse,
    CrawlerStatusItem,
    CrawlerStatusResponse,
    SchedulerJob,
    SchedulerJobsResponse,
    TriggerCrawlerResponse,
    UserStatusUpdate,
)
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/admin", tags=["Admin"])

PLATFORMS = ["daangn", "bunjang", "joongna"]


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    total_users = (await db.execute(select(func.count(User.user_id)).where(User.deleted_at.is_(None)))).scalar_one()
    deleted_users = (await db.execute(select(func.count(User.user_id)).where(User.deleted_at.isnot(None)))).scalar_one()

    today = datetime.now(timezone.utc).date()
    active_today = 0  # TODO: last_login 컬럼 추가 시 구현

    total_items = (await db.execute(select(func.count(Item.item_id)))).scalar_one()
    added_today = (
        await db.execute(
            select(func.count(Item.item_id)).where(func.date(Item.created_at) == today)
        )
    ).scalar_one()

    total_wl = (await db.execute(select(func.count(Watchlist.watch_id)))).scalar_one()
    active_wl = (await db.execute(select(func.count(Watchlist.watch_id)).where(Watchlist.is_active == True))).scalar_one()

    alerts_today = (
        await db.execute(
            select(func.count(Alert.alert_id)).where(func.date(Alert.triggered_at) == today)
        )
    ).scalar_one()

    return AdminStatsResponse(
        users={"total": total_users, "active_today": active_today, "deleted": deleted_users},
        listings={"total": total_items, "added_today": added_today},
        watchlists={"total": total_wl, "active": active_wl},
        alerts_sent_today=alerts_today,
    )


@router.get("/crawlers/status", response_model=CrawlerStatusResponse)
async def get_crawler_status(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = []
    for platform in PLATFORMS:
        log = (
            await db.execute(
                select(CrawlerLog).where(CrawlerLog.platform == platform).order_by(CrawlerLog.started_at.desc()).limit(1)
            )
        ).scalar_one_or_none()

        result.append(CrawlerStatusItem(
            platform=platform,
            last_run_at=log.started_at if log else None,
            status=log.status if log else None,
            items_upserted=log.items_upserted if log else 0,
            duration_sec=log.duration_sec if log else None,
            error=log.error if log else None,
        ))

    return CrawlerStatusResponse(crawlers=result)


@router.post("/crawlers/{platform}/trigger", response_model=TriggerCrawlerResponse, status_code=202)
async def trigger_crawler(
    platform: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if platform not in PLATFORMS:
        raise BadRequest(f"지원하지 않는 플랫폼입니다. 가능: {', '.join(PLATFORMS)}")

    # 비동기로 크롤러 실행 (background task)
    from fastapi import BackgroundTasks
    from app.crawlers.base import run_crawler_by_platform
    import asyncio

    job_id = f"crawl-{platform}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    asyncio.create_task(run_crawler_by_platform(platform, db))

    return TriggerCrawlerResponse(message=f"{platform} 크롤링이 시작되었습니다.", job_id=job_id)


@router.get("/scheduler/jobs", response_model=SchedulerJobsResponse)
async def get_scheduler_jobs(_: User = Depends(get_current_admin)):
    from app.core.scheduler import get_job_info
    jobs = get_job_info()
    return SchedulerJobsResponse(jobs=[SchedulerJob(**j) for j in jobs])


@router.get("/users", response_model=AdminUsersResponse)
async def list_users(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    if q:
        query = query.where(User.email.ilike(f"%{q}%") | User.nickname.ilike(f"%{q}%"))
    if status == "deleted":
        query = query.where(User.deleted_at.isnot(None))
    elif status == "suspended":
        query = query.where(User.status == UserStatus.suspended, User.deleted_at.is_(None))
    elif status == "active":
        query = query.where(User.status == UserStatus.active, User.deleted_at.is_(None))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    users = (await db.execute(query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()

    items = []
    for u in users:
        user_status = "deleted" if u.deleted_at else u.status.value
        items.append(AdminUserItem(
            user_id=u.user_id,
            email=u.email,
            nickname=u.nickname,
            is_email_verified=u.is_email_verified,
            status=user_status,
            created_at=u.created_at,
        ))

    return AdminUsersResponse(total=total, users=items)


@router.patch("/users/{user_id}/status", response_model=MessageResponse)
async def update_user_status(
    user_id: int,
    body: UserStatusUpdate,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise NotFound("사용자를 찾을 수 없습니다.")

    if body.status == "suspended":
        user.status = UserStatus.suspended
    elif body.status == "active":
        user.status = UserStatus.active
    else:
        raise BadRequest("유효하지 않은 상태값입니다.")

    await db.commit()
    return MessageResponse(message=f"사용자 상태가 {body.status}으로 변경되었습니다.")
