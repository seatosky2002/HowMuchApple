from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_admin
from app.core.exceptions import BadRequest, Conflict, NotFound
from app.db.models.alert import Alert, Watchlist
from app.db.models.category import Attribute, AttributeOption, Category, CategoryAttribute
from app.db.models.crawler import CrawlerLog
from app.db.models.item import Item
from app.db.models.sku import SKU
from app.db.models.user import User, UserStatus
from app.db.session import get_db
from app.schemas.admin import (
    AdminCategoriesResponse,
    AdminCategoryAttributeCreate,
    AdminCategoryItem,
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
from app.schemas.category import AttributeDetail, AttributeOptionItem, CategoryAttributesResponse
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/admin", tags=["Admin"])

PLATFORMS = ["daangn", "bunjang", "joongna"]


def _build_attribute_detail(category_attribute: CategoryAttribute) -> AttributeDetail:
    attr = category_attribute.attribute
    return AttributeDetail(
        attribute_id=attr.attribute_id,
        code=attr.code,
        label=attr.label,
        datatype=attr.datatype,
        unit=attr.unit,
        is_required=category_attribute.is_required,
        display_group=category_attribute.display_group,
        sort_order=category_attribute.sort_order,
        options=[AttributeOptionItem.model_validate(o) for o in attr.options],
    )


async def _load_category_with_attributes(db: AsyncSession, category_id: int) -> Category:
    result = await db.execute(
        select(Category)
        .where(Category.category_id == category_id)
        .options(
            selectinload(Category.attributes)
            .selectinload(CategoryAttribute.attribute)
            .selectinload(Attribute.options)
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        raise NotFound("카테고리를 찾을 수 없습니다.")
    return category


def _category_attributes_response(category: Category) -> CategoryAttributesResponse:
    category_attributes = sorted(category.attributes, key=lambda ca: ca.sort_order)
    return CategoryAttributesResponse(
        category_id=category.category_id,
        name=category.name,
        attributes=[_build_attribute_detail(ca) for ca in category_attributes],
    )


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


@router.get("/categories", response_model=AdminCategoriesResponse)
async def list_admin_categories(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Category)
        .options(
            selectinload(Category.attributes)
            .selectinload(CategoryAttribute.attribute)
            .selectinload(Attribute.options)
        )
        .order_by(Category.category_id)
    )
    categories = result.scalars().all()
    return AdminCategoriesResponse(
        categories=[
            AdminCategoryItem(
                category_id=category.category_id,
                name=category.name,
                attributes=[
                    _build_attribute_detail(ca)
                    for ca in sorted(category.attributes, key=lambda item: item.sort_order)
                ],
            )
            for category in categories
        ]
    )


@router.post(
    "/categories/{category_id}/attributes",
    response_model=CategoryAttributesResponse,
    status_code=201,
)
async def add_category_attribute(
    category_id: int,
    body: AdminCategoryAttributeCreate,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    category = await db.get(Category, category_id)
    if not category:
        raise NotFound("카테고리를 찾을 수 없습니다.")

    if body.attribute_id is not None:
        attribute = await db.get(Attribute, body.attribute_id)
        if not attribute:
            raise NotFound("속성을 찾을 수 없습니다.")
    else:
        existing_attribute = (
            await db.execute(select(Attribute).where(Attribute.code == body.code))
        ).scalar_one_or_none()
        if existing_attribute:
            raise Conflict("이미 존재하는 속성 코드입니다. 기존 속성은 attribute_id로 연결해주세요.")

        attribute = Attribute(
            code=body.code,
            label=body.label,
            datatype=body.datatype,
            unit=body.unit,
            description=body.description,
        )
        db.add(attribute)
        await db.flush()

    existing_mapping = (
        await db.execute(
            select(CategoryAttribute).where(
                CategoryAttribute.category_id == category_id,
                CategoryAttribute.attribute_id == attribute.attribute_id,
            )
        )
    ).scalar_one_or_none()
    if existing_mapping:
        raise Conflict("이미 이 카테고리에 연결된 속성입니다.")

    for option in body.options:
        duplicate_option = (
            await db.execute(
                select(AttributeOption).where(
                    AttributeOption.attribute_id == attribute.attribute_id,
                    AttributeOption.value == option.value,
                )
            )
        ).scalar_one_or_none()
        if duplicate_option:
            continue
        db.add(
            AttributeOption(
                attribute_id=attribute.attribute_id,
                value=option.value,
                sort_order=option.sort_order,
            )
        )

    db.add(
        CategoryAttribute(
            category_id=category_id,
            attribute_id=attribute.attribute_id,
            is_required=body.is_required,
            display_group=body.display_group,
            sort_order=body.sort_order,
        )
    )

    await db.commit()
    category = await _load_category_with_attributes(db, category_id)
    return _category_attributes_response(category)
