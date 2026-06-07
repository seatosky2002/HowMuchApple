from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import Forbidden, NotFound
from app.db.models.alert import Alert, Watchlist
from app.db.models.sku import SKU, SKUAttribute
from app.db.models.region import EMD, SGG
from app.db.models.user import User
from app.schemas.watchlist import WatchlistCreateRequest, WatchlistUpdateRequest
from app.services.sku import build_sku_label


def _channels_from_watchlist(w: Watchlist) -> list[str]:
    ch = []
    if w.alert_email:
        ch.append("email")
    if w.alert_sms:
        ch.append("sms")
    return ch


async def _build_watchlist_item(db: AsyncSession, w: Watchlist) -> dict:
    sku = await db.get(
        SKU,
        w.sku_id,
        options=[selectinload(SKU.category),
                 selectinload(SKU.attributes).selectinload(SKUAttribute.option)],
    )
    spec_label = await build_sku_label(sku) if sku else ""
    product = sku.category.name if sku and sku.category else ""

    region = None
    if w.region_id:
        emd = await db.get(EMD, w.region_id)
        if emd:
            sgg = await db.get(SGG, emd.sgg_id)
            region = {"sgg": sgg.name if sgg else None, "emd": emd.name}

    latest_result = await db.execute(
        select(Alert)
        .where(Alert.watch_id == w.watch_id)
        .order_by(Alert.triggered_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()

    return {
        "watch_id": w.watch_id,
        "sku_id": w.sku_id,
        "label": w.label,
        "product": product,
        "spec_label": spec_label,
        "region": region,
        "max_price": w.max_price,
        "is_active": w.is_active,
        "alert_channels": _channels_from_watchlist(w),
        "latest_alert": {
            "alert_id": latest.alert_id,
            "triggered_at": latest.triggered_at,
            "is_read": latest.is_read,
        } if latest else None,
        "created_at": w.created_at,
    }


async def list_watchlist(db: AsyncSession, user: User) -> list[dict]:
    result = await db.execute(
        select(Watchlist)
        .where(Watchlist.user_id == user.user_id)
        .order_by(Watchlist.created_at.desc())
    )
    items = result.scalars().all()
    return [await _build_watchlist_item(db, w) for w in items]


async def create_watchlist(db: AsyncSession, user: User, data: WatchlistCreateRequest) -> Watchlist:
    w = Watchlist(
        user_id=user.user_id,
        sku_id=data.sku_id,
        region_id=data.region_id,
        max_price=data.max_price,
        label=data.label,
        alert_email="email" in data.alert_channels,
        alert_sms="sms" in data.alert_channels,
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return w


async def get_watchlist(db: AsyncSession, user: User, watch_id: int) -> dict:
    w = await db.get(Watchlist, watch_id)
    if not w or w.user_id != user.user_id:
        raise NotFound("찜 항목을 찾을 수 없습니다.")

    sku = await db.get(
        SKU,
        w.sku_id,
        options=[selectinload(SKU.attributes).selectinload(SKUAttribute.attribute),
                 selectinload(SKU.attributes).selectinload(SKUAttribute.option)],
    )
    attrs = []
    if sku:
        for sa in sorted(sku.attributes, key=lambda x: x.attribute_id):
            attrs.append({
                "code": sa.attribute.code,
                "value": sa.option.value if sa.option else sa.value_text or "",
            })

    region = None
    if w.region_id:
        emd = await db.get(EMD, w.region_id)
        if emd:
            sgg = await db.get(SGG, emd.sgg_id)
            region = {"sd": None, "sgg": sgg.name if sgg else None, "emd": emd.name}

    return {
        "watch_id": w.watch_id,
        "sku_id": w.sku_id,
        "spec_label": await build_sku_label(sku) if sku else "",
        "attributes": attrs,
        "region": region,
        "max_price": w.max_price,
        "is_active": w.is_active,
        "alert_channels": _channels_from_watchlist(w),
        "created_at": w.created_at,
        "updated_at": w.updated_at,
    }


async def update_watchlist(db: AsyncSession, user: User, watch_id: int, data: WatchlistUpdateRequest) -> Watchlist:
    w = await db.get(Watchlist, watch_id)
    if not w or w.user_id != user.user_id:
        raise NotFound("찜 항목을 찾을 수 없습니다.")

    if data.max_price is not None:
        w.max_price = data.max_price
    if data.label is not None:
        w.label = data.label
    if data.alert_channels is not None:
        w.alert_email = "email" in data.alert_channels
        w.alert_sms = "sms" in data.alert_channels

    await db.commit()
    return w


async def toggle_active(db: AsyncSession, user: User, watch_id: int) -> Watchlist:
    w = await db.get(Watchlist, watch_id)
    if not w or w.user_id != user.user_id:
        raise NotFound("찜 항목을 찾을 수 없습니다.")
    w.is_active = not w.is_active
    await db.commit()
    return w


async def delete_watchlist(db: AsyncSession, user: User, watch_id: int) -> None:
    w = await db.get(Watchlist, watch_id)
    if not w or w.user_id != user.user_id:
        raise NotFound("찜 항목을 찾을 수 없습니다.")
    await db.delete(w)
    await db.commit()


async def get_watchlist_alerts(db: AsyncSession, user: User, watch_id: int, page: int, page_size: int) -> dict:
    w = await db.get(Watchlist, watch_id)
    if not w or w.user_id != user.user_id:
        raise NotFound("찜 항목을 찾을 수 없습니다.")

    total = (
        await db.execute(select(func.count(Alert.alert_id)).where(Alert.watch_id == watch_id))
    ).scalar_one()

    alerts = (
        await db.execute(
            select(Alert)
            .where(Alert.watch_id == watch_id)
            .order_by(Alert.triggered_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    items = []
    for a in alerts:
        item_price = None
        if a.item_id:
            item = await db.get(__import__("app.db.models.item", fromlist=["Item"]).Item, a.item_id)
            item_price = item.price if item else None
        items.append({
            "alert_id": a.alert_id,
            "message": a.message,
            "item_id": a.item_id,
            "listing_price": item_price,
            "is_read": a.is_read,
            "triggered_at": a.triggered_at,
        })

    return {"watch_id": watch_id, "total": total, "alerts": items}
