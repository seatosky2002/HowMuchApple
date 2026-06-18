from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.item import Item, ItemStatus
from app.db.models.region import EMD, SGG
from app.db.models.sku import PriceStats, SKU, SKUAttribute


async def get_summary(db: AsyncSession, sku_id: int, emd_id: int | None) -> dict:
    from app.services.sku import get_sku_with_price, get_price_trend, build_sku_label

    sku, price_summary = await get_sku_with_price(db, sku_id, emd_id)
    label = await build_sku_label(sku)

    region_name = "서울 전체"
    if emd_id:
        emd = await db.get(EMD, emd_id)
        if emd:
            sgg = await db.get(SGG, emd.sgg_id)
            region_name = f"{sgg.name} {emd.name}" if sgg else emd.name

    trend_stats = await get_price_trend(db, sku_id, emd_id, "4w")
    chart_data = [
        {"bucket_ts": s.bucket_ts.strftime("%Y-%m-%d"), "avg_price": float(s.avg_price)}
        for s in trend_stats
    ]
    change_rate = 0.0
    if len(chart_data) >= 2:
        first, last = float(chart_data[0]["avg_price"]), float(chart_data[-1]["avg_price"])
        if first:
            change_rate = round((last - first) / first * 100, 1)

    breakdown_query = (
        select(
            SGG.name.label("sgg_name"),
            EMD.name.label("emd_name"),
            func.avg(Item.price).label("avg"),
            func.count(Item.item_id).label("cnt"),
        )
        .select_from(Item)
        .join(EMD, Item.emd_id == EMD.emd_id)
        .join(SGG, EMD.sgg_id == SGG.sgg_id)
        .where(Item.sku_id == sku_id, Item.status == ItemStatus.active)
        .group_by(SGG.name, EMD.name)
        .order_by(func.avg(Item.price))
        .limit(10)
    )
    breakdown_rows = (await db.execute(breakdown_query)).all()
    regional_breakdown = [
        {"sgg": r.sgg_name, "emd": r.emd_name, "avg_price": float(r.avg), "listing_count": int(r.cnt)}
        for r in breakdown_rows
    ]

    return {
        "sku_id": sku_id,
        "label": label,
        "region": region_name,
        "summary": price_summary,
        "price_trend": {
            "period": "4w",
            "change_rate": change_rate,
            "chart_data": chart_data,
        },
        "regional_breakdown": regional_breakdown,
    }


async def get_listings(
    db: AsyncSession,
    sku_id: int,
    emd_id: int | None,
    page: int,
    page_size: int,
    sort: str,
    source: str | None,
) -> dict:
    query = (
        select(Item)
        .where(Item.sku_id == sku_id, Item.status == ItemStatus.active)
    )
    if emd_id:
        query = query.where(Item.emd_id == emd_id)
    if source:
        query = query.where(Item.source == source)

    sort_map = {
        "price_asc": Item.price.asc(),
        "price_desc": Item.price.desc(),
        "newest": Item.created_at.desc(),
    }
    query = query.order_by(sort_map.get(sort, Item.price.asc()))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    items = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    listings = []
    for item in items:
        emd = await db.get(EMD, item.emd_id) if item.emd_id else None
        sgg = await db.get(SGG, emd.sgg_id) if emd else None
        listings.append({
            "item_id": item.item_id,
            "listing_price": item.price,
            "title": item.title,
            "sgg": sgg.name if sgg else item.region_sgg,
            "emd": emd.name if emd else item.region_emd,
            "source": item.source,
            "source_url": item.url,
            "status": item.status.value,
            "created_at": item.created_at,
        })

    return {"total": total, "page": page, "page_size": page_size, "listings": listings}


async def get_trending(db: AsyncSession, category_id: int | None, limit: int, direction: str) -> list[dict]:
    from datetime import datetime, timedelta, timezone

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)

    recent = (
        select(PriceStats.sku_id, func.avg(PriceStats.avg_price).label("recent_avg"))
        .where(PriceStats.bucket_ts >= week_ago)
        .group_by(PriceStats.sku_id)
        .subquery()
    )
    prev = (
        select(PriceStats.sku_id, func.avg(PriceStats.avg_price).label("prev_avg"))
        .where(PriceStats.bucket_ts >= two_weeks_ago, PriceStats.bucket_ts < week_ago)
        .group_by(PriceStats.sku_id)
        .subquery()
    )

    query = (
        select(SKU, recent.c.recent_avg, prev.c.prev_avg)
        .join(recent, SKU.sku_id == recent.c.sku_id)
        .join(prev, SKU.sku_id == prev.c.sku_id)
        .options(selectinload(SKU.attributes).selectinload(SKUAttribute.option))
    )
    if category_id:
        query = query.where(SKU.category_id == category_id)

    rows = (await db.execute(query)).all()

    from app.services.sku import build_sku_label

    result = []
    for sku, recent_avg, prev_avg in rows:
        if not prev_avg:
            continue
        change_rate = round((float(recent_avg) - float(prev_avg)) / float(prev_avg) * 100, 1)
        dir_val = "drop" if change_rate < 0 else "rise"
        if direction != "both" and dir_val != direction:
            continue
        result.append({
            "sku_id": sku.sku_id,
            "label": await build_sku_label(sku),
            "avg_price": float(recent_avg),
            "change_rate": change_rate,
            "direction": dir_val,
        })

    result.sort(key=lambda x: abs(x["change_rate"]), reverse=True)
    return result[:limit]


async def get_popular(db: AsyncSession, category_id: int | None, limit: int) -> list[dict]:
    query = (
        select(SKU, func.avg(Item.price).label("avg"), func.count(Item.item_id).label("cnt"))
        .join(Item, Item.sku_id == SKU.sku_id)
        .where(Item.status == ItemStatus.active)
        .options(
            selectinload(SKU.attributes).selectinload(SKUAttribute.option),
        )
        .group_by(SKU.sku_id)
        .order_by(func.count(Item.item_id).desc(), SKU.search_count.desc())
        .limit(limit)
    )
    if category_id:
        query = query.where(SKU.category_id == category_id)

    rows = (await db.execute(query)).all()

    from app.services.sku import build_sku_label

    result = []
    for sku, avg_price, _ in rows:
        result.append({
            "sku_id": sku.sku_id,
            "label": await build_sku_label(sku),
            "avg_price": round(float(avg_price or 0)),
            "search_count": sku.search_count,
        })
    return result


async def get_platform_compare(db: AsyncSession, sku_id: int, emd_id: int | None) -> list[dict]:
    query = (
        select(Item.source, func.avg(Item.price).label("avg"), func.count(Item.item_id).label("cnt"))
        .where(Item.sku_id == sku_id, Item.status == ItemStatus.active)
        .group_by(Item.source)
    )
    if emd_id:
        query = query.where(Item.emd_id == emd_id)

    rows = (await db.execute(query)).all()
    return [{"source": r.source, "avg_price": float(r.avg), "listing_count": r.cnt} for r in rows]
