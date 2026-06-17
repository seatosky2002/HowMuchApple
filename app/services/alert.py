from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFound
from app.db.models.alert import Alert, Watchlist
from app.db.models.item import Item
from app.db.models.sku import SKU, SKUAttribute
from app.db.models.user import User
from app.services.sku import build_sku_label


async def list_alerts(
    db: AsyncSession,
    user: User,
    is_read: bool | None,
    watch_id: int | None,
    from_date: datetime | None,
    page: int,
    page_size: int,
) -> dict:
    query = select(Alert).where(Alert.user_id == user.user_id)
    if is_read is not None:
        query = query.where(Alert.is_read == is_read)
    if watch_id:
        query = query.where(Alert.watch_id == watch_id)
    if from_date:
        query = query.where(Alert.triggered_at >= from_date)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    unread = (
        await db.execute(
            select(func.count(Alert.alert_id)).where(Alert.user_id == user.user_id, Alert.is_read == False)
        )
    ).scalar_one()

    alerts = (
        await db.execute(
            query.order_by(Alert.triggered_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    items = []
    for a in alerts:
        watchlist = await db.get(
            Watchlist,
            a.watch_id,
            options=[selectinload(Watchlist.sku).selectinload(SKU.attributes).selectinload(SKUAttribute.option)],
        )
        spec_label = await build_sku_label(watchlist.sku) if watchlist and watchlist.sku else ""
        item_detail = None
        if a.item_id:
            item = await db.get(Item, a.item_id)
            if item:
                item_detail = {
                    "item_id": item.item_id,
                    "listing_price": item.price,
                    "source": item.source,
                    "source_url": item.url,
                }
        items.append({
            "alert_id": a.alert_id,
            "watch_id": a.watch_id,
            "watch_label": watchlist.label if watchlist else None,
            "spec_label": spec_label,
            "message": a.message,
            "item": item_detail,
            "is_read": a.is_read,
            "triggered_at": a.triggered_at,
        })

    return {"total": total, "unread": unread, "alerts": items}


async def unread_count(db: AsyncSession, user: User) -> int:
    return (
        await db.execute(
            select(func.count(Alert.alert_id)).where(Alert.user_id == user.user_id, Alert.is_read == False)
        )
    ).scalar_one()


async def mark_read(db: AsyncSession, user: User, alert_id: int) -> None:
    alert = await db.get(Alert, alert_id)
    if not alert or alert.user_id != user.user_id:
        raise NotFound("알림을 찾을 수 없습니다.")
    alert.is_read = True
    await db.commit()


async def mark_all_read(db: AsyncSession, user: User) -> None:
    alerts = (
        await db.execute(select(Alert).where(Alert.user_id == user.user_id, Alert.is_read == False))
    ).scalars().all()
    for a in alerts:
        a.is_read = True
    await db.commit()


async def delete_alert(db: AsyncSession, user: User, alert_id: int) -> None:
    alert = await db.get(Alert, alert_id)
    if not alert or alert.user_id != user.user_id:
        raise NotFound("알림을 찾을 수 없습니다.")
    await db.delete(alert)
    await db.commit()


async def bulk_delete_alerts(db: AsyncSession, user: User, alert_ids: list[int] | None) -> int:
    if alert_ids:
        result = await db.execute(
            delete(Alert).where(Alert.user_id == user.user_id, Alert.alert_id.in_(alert_ids))
        )
    else:
        result = await db.execute(delete(Alert).where(Alert.user_id == user.user_id))
    await db.commit()
    return result.rowcount


async def process_watchlist_alerts(db: AsyncSession) -> int:
    """스케줄러가 호출. active watchlist를 순회하며 max_price 이하 매물 발생 시 alert 생성."""
    active = (
        await db.execute(
            select(Watchlist)
            .where(Watchlist.is_active == True)
            .options(
                selectinload(Watchlist.user),
                selectinload(Watchlist.sku).selectinload(SKU.attributes).selectinload(SKUAttribute.option),
            )
        )
    ).scalars().all()

    created = 0
    for w in active:
        if not w.user.watchlist_alerts_enabled:
            continue

        items = (
            await db.execute(
                select(Item)
                .where(
                    Item.sku_id == w.sku_id,
                    Item.price <= w.max_price,
                    Item.status == "active",
                )
            )
        ).scalars().all()

        if w.emd_id:
            items = [i for i in items if i.emd_id == w.emd_id]

        for item in items:
            existing = (
                await db.execute(
                    select(Alert).where(Alert.watch_id == w.watch_id, Alert.item_id == item.item_id)
                )
            ).scalar_one_or_none()
            if existing:
                continue

            spec = await build_sku_label(w.sku) if w.sku else ""
            message = f"{spec} — {item.price:,}원 매물이 등록되었습니다."

            alert = Alert(
                user_id=w.user_id,
                watch_id=w.watch_id,
                item_id=item.item_id,
                message=message,
                sent_email=False,
                sent_sms=False,
            )
            db.add(alert)
            await db.flush()

            from app.services.notification import send_alert_email, send_sms
            if w.alert_email and w.user.alert_email and w.user.is_email_verified:
                await send_alert_email(w.user.email, message, item.url)
                alert.sent_email = True
            if w.alert_sms and w.user.alert_sms and w.user.is_phone_verified and w.user.phone:
                await send_sms(w.user.phone, message)
                alert.sent_sms = True

            created += 1

    await db.commit()
    return created
