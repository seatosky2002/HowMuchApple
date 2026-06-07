from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequest, NotFound
from app.db.models.category import Category, Attribute, AttributeOption, CategoryAttribute
from app.db.models.sku import SKU, SKUAttribute, PriceStats
from app.schemas.sku import AttributeInput


def _make_fingerprint(category_id: int, sorted_attr_options: list[tuple[int, int]]) -> str:
    parts = [str(category_id)] + [f"{aid}:{oid}" for aid, oid in sorted_attr_options]
    return "-".join(parts)


async def resolve_sku(db: AsyncSession, category_id: int, attributes: list[AttributeInput]) -> SKU:
    category = await db.get(Category, category_id)
    if not category:
        raise NotFound("카테고리를 찾을 수 없습니다.")

    sorted_pairs = sorted((a.attribute_id, a.option_id) for a in attributes)
    fingerprint = _make_fingerprint(category_id, sorted_pairs)

    result = await db.execute(
        select(SKU)
        .where(SKU.fingerprint == fingerprint)
        .options(selectinload(SKU.attributes).selectinload(SKUAttribute.attribute),
                 selectinload(SKU.attributes).selectinload(SKUAttribute.option))
    )
    sku = result.scalar_one_or_none()
    if sku:
        sku.search_count += 1
        await db.commit()
        return sku

    # Validate all option_ids exist
    for attr_id, opt_id in sorted_pairs:
        opt = await db.get(AttributeOption, opt_id)
        if not opt or opt.attribute_id != attr_id:
            raise BadRequest(f"option_id {opt_id}가 attribute_id {attr_id}에 속하지 않습니다.")

    sku = SKU(category_id=category_id, fingerprint=fingerprint, search_count=1)
    db.add(sku)
    await db.flush()

    for attr_id, opt_id in sorted_pairs:
        sku_attr = SKUAttribute(sku_id=sku.sku_id, attribute_id=attr_id, option_id=opt_id)
        db.add(sku_attr)

    await db.commit()

    result = await db.execute(
        select(SKU)
        .where(SKU.sku_id == sku.sku_id)
        .options(selectinload(SKU.attributes).selectinload(SKUAttribute.attribute),
                 selectinload(SKU.attributes).selectinload(SKUAttribute.option))
    )
    return result.scalar_one()


async def build_sku_label(sku: SKU) -> str:
    parts = []
    for sa in sorted(sku.attributes, key=lambda x: x.attribute_id):
        if sa.option and sa.option.value:
            parts.append(sa.option.value)
        elif sa.value_text:
            parts.append(sa.value_text)
    return " ".join(parts)


async def get_sku_with_price(db: AsyncSession, sku_id: int) -> tuple[SKU, dict]:
    result = await db.execute(
        select(SKU)
        .where(SKU.sku_id == sku_id)
        .options(
            selectinload(SKU.category),
            selectinload(SKU.attributes).selectinload(SKUAttribute.attribute),
            selectinload(SKU.attributes).selectinload(SKUAttribute.option),
        )
    )
    sku = result.scalar_one_or_none()
    if not sku:
        raise NotFound("SKU를 찾을 수 없습니다.")

    stats_result = await db.execute(
        select(
            func.avg(PriceStats.avg_price).label("avg"),
            func.min(PriceStats.min_price).label("min"),
            func.max(PriceStats.max_price).label("max"),
            func.sum(PriceStats.items_num).label("count"),
            func.max(PriceStats.bucket_ts).label("updated_at"),
        ).where(PriceStats.sku_id == sku_id)
    )
    row = stats_result.one()

    price_summary = {
        "avg_price": float(row.avg or 0),
        "min_price": int(row.min or 0),
        "max_price": int(row.max or 0),
        "listing_count": int(row.count or 0),
        "updated_at": row.updated_at,
    }
    return sku, price_summary


async def get_price_trend(db: AsyncSession, sku_id: int, region_id: int | None, period: str) -> list[PriceStats]:
    from datetime import timedelta, datetime, timezone

    period_map = {"4w": 28, "8w": 56, "3m": 90, "6m": 180, "1y": 365}
    days = period_map.get(period, 28)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    query = select(PriceStats).where(PriceStats.sku_id == sku_id, PriceStats.bucket_ts >= since)
    if region_id:
        query = query.where(PriceStats.region_id == region_id)

    result = await db.execute(query.order_by(PriceStats.bucket_ts))
    return result.scalars().all()
