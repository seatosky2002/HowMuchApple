from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequest, NotFound
from app.db.models.category import Category, Attribute, AttributeOption, CategoryAttribute
from app.db.models.item import Item, ItemStatus
from app.db.models.sku import SKU, SKUAttribute, PriceStats
from app.schemas.sku import AttributeInput
from app.services.attribute_extractor import REQUIRED_CODES


@dataclass
class PriceTrendStat:
    bucket_ts: date | datetime
    avg_price: float
    items_num: int


def _make_fingerprint(category_id: int, sorted_attr_options: list[tuple[int, int]]) -> str:
    parts = [str(category_id)] + [f"{aid}:{oid}" for aid, oid in sorted_attr_options]
    return "-".join(parts)


async def _crawler_fingerprint(
    db: AsyncSession, category: Category, sorted_pairs: list[tuple[int, int]]
) -> str | None:
    """SkuAssigner(attribute_extractor.fingerprint)와 동일한 값 기반 fingerprint.

    크롤러가 매물을 배정하는 SKU와 검색이 만드는 SKU가 서로 다른 fingerprint
    형식을 쓰면 같은 제품이 이중 등록되고 검색 결과가 항상 0건이 된다. 검색도
    반드시 이 형식으로 조회/생성해야 한다. required 코드가 모두 없으면 None.
    """
    required = REQUIRED_CODES.get(category.name)
    if not required:
        return None

    values: dict[str, str] = {}
    for attr_id, opt_id in sorted_pairs:
        opt = await db.get(AttributeOption, opt_id)
        if not opt or opt.attribute_id != attr_id:
            raise BadRequest(f"option_id {opt_id}가 attribute_id {attr_id}에 속하지 않습니다.")
        attr = await db.get(Attribute, attr_id)
        if attr:
            values[attr.code] = opt.value

    if not all(code in values for code in required):
        return None
    parts = "|".join(f"{code}={values[code]}" for code in required)
    return f"{category.category_id}:{parts}"


async def resolve_sku(db: AsyncSession, category_id: int, attributes: list[AttributeInput]) -> SKU:
    category = await db.get(Category, category_id)
    if not category:
        raise NotFound("카테고리를 찾을 수 없습니다.")

    sorted_pairs = sorted((a.attribute_id, a.option_id) for a in attributes)
    fingerprint = await _crawler_fingerprint(db, category, sorted_pairs) or _make_fingerprint(
        category_id, sorted_pairs
    )

    result = await db.execute(
        select(SKU)
        .where(SKU.fingerprint == fingerprint)
        .options(
            selectinload(SKU.category),
            selectinload(SKU.attributes).selectinload(SKUAttribute.attribute),
            selectinload(SKU.attributes).selectinload(SKUAttribute.option),
        )
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
        .options(
            selectinload(SKU.category),
            selectinload(SKU.attributes).selectinload(SKUAttribute.attribute),
            selectinload(SKU.attributes).selectinload(SKUAttribute.option),
        )
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


def _percentile(sorted_prices: list[int], p: float) -> float:
    idx = (len(sorted_prices) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(sorted_prices) - 1)
    frac = idx - lo
    return sorted_prices[lo] * (1 - frac) + sorted_prices[hi] * frac


async def get_price_fences(
    db: AsyncSession, sku_id: int, emd_id: int | None = None
) -> tuple[int, int] | None:
    """활성 매물 가격의 IQR 펜스(Q1-1.5·IQR, Q3+1.5·IQR).

    내구제·계정거래류 비매물성 글(예: 17e 256GB에 16만원)이 제목 필터를 뚫고
    들어와 평균/최저가를 왜곡하므로, 시세 집계에서는 펜스 밖 가격을 제외한다.
    표본 5개 미만이면 판단 불가로 None(필터 없음).
    """
    query = select(Item.price).where(Item.sku_id == sku_id, Item.status == ItemStatus.active)
    if emd_id:
        query = query.where(Item.emd_id == emd_id)
    prices = sorted((await db.execute(query)).scalars().all())
    if len(prices) < 5:
        return None
    q1 = _percentile(prices, 0.25)
    q3 = _percentile(prices, 0.75)
    median = prices[len(prices) // 2]
    # 동일가 매물이 몰려 IQR이 0에 수렴해도 정상 스프레드(±는 중앙값의 12%)는 남긴다
    iqr = max(q3 - q1, median * 0.12)
    return max(int(q1 - 1.5 * iqr), 0), int(q3 + 1.5 * iqr)


async def get_sku_with_price(db: AsyncSession, sku_id: int, emd_id: int | None = None) -> tuple[SKU, dict]:
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

    item_query = select(
        func.avg(Item.price).label("avg"),
        func.min(Item.price).label("min"),
        func.max(Item.price).label("max"),
        func.count(Item.item_id).label("count"),
        func.max(Item.updated_at).label("updated_at"),
    ).where(Item.sku_id == sku_id, Item.status == ItemStatus.active)
    if emd_id:
        item_query = item_query.where(Item.emd_id == emd_id)
    fences = await get_price_fences(db, sku_id, emd_id)
    if fences:
        item_query = item_query.where(Item.price.between(*fences))

    item_row = (await db.execute(item_query)).one()
    if int(item_row.count or 0) > 0:
        return sku, {
            "avg_price": round(float(item_row.avg or 0)),
            "min_price": int(item_row.min or 0),
            "max_price": int(item_row.max or 0),
            "listing_count": int(item_row.count or 0),
            "updated_at": item_row.updated_at,
        }

    stats_query = select(
        func.avg(PriceStats.avg_price).label("avg"),
        func.min(PriceStats.min_price).label("min"),
        func.max(PriceStats.max_price).label("max"),
        func.sum(PriceStats.items_num).label("count"),
        func.max(PriceStats.bucket_ts).label("updated_at"),
    ).where(PriceStats.sku_id == sku_id)
    if emd_id:
        stats_query = stats_query.where(PriceStats.emd_id == emd_id)

    stats_result = await db.execute(
        stats_query
    )
    row = stats_result.one()

    price_summary = {
        "avg_price": round(float(row.avg or 0)),
        "min_price": int(row.min or 0),
        "max_price": int(row.max or 0),
        "listing_count": int(row.count or 0),
        "updated_at": row.updated_at,
    }
    return sku, price_summary


async def get_price_trend(db: AsyncSession, sku_id: int, emd_id: int | None, period: str) -> list[PriceTrendStat]:
    period_map = {"4w": 28, "8w": 56, "3m": 90, "6m": 180, "1y": 365}
    days = period_map.get(period, 28)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # 일별 스냅샷(price_stats) 우선. item.updated_at은 크롤 upsert가 매일 갱신해
    # 전 매물이 최신 크롤 날짜로 뭉치므로 item 기반으로는 과거 추이를 만들 수 없다.
    if emd_id:
        stats_query = (
            select(
                PriceStats.bucket_ts.label("bucket_ts"),
                PriceStats.avg_price.label("avg_price"),
                PriceStats.items_num.label("items_num"),
            )
            .where(PriceStats.sku_id == sku_id, PriceStats.emd_id == emd_id, PriceStats.bucket_ts >= since)
            .order_by(PriceStats.bucket_ts)
        )
    else:
        stats_query = (
            select(
                PriceStats.bucket_ts.label("bucket_ts"),
                (func.sum(PriceStats.sum_price) / func.sum(PriceStats.items_num)).label("avg_price"),
                func.sum(PriceStats.items_num).label("items_num"),
            )
            .where(PriceStats.sku_id == sku_id, PriceStats.bucket_ts >= since)
            .group_by(PriceStats.bucket_ts)
            .order_by(PriceStats.bucket_ts)
        )
    stats_rows = (await db.execute(stats_query)).all()
    stats = [
        PriceTrendStat(
            bucket_ts=row.bucket_ts,
            avg_price=round(float(row.avg_price or 0)),
            items_num=int(row.items_num or 0),
        )
        for row in stats_rows
    ]
    if len(stats) >= 2:
        return stats

    # 스냅샷이 쌓이기 전 폴백: 최초 수집일(created_at) 기준 일별 평균
    item_query = select(
        func.date(Item.created_at).label("bucket_ts"),
        func.avg(Item.price).label("avg_price"),
        func.count(Item.item_id).label("items_num"),
    ).where(
        Item.sku_id == sku_id,
        Item.status == ItemStatus.active,
        Item.created_at >= since,
    )
    if emd_id:
        item_query = item_query.where(Item.emd_id == emd_id)
    fences = await get_price_fences(db, sku_id, emd_id)
    if fences:
        item_query = item_query.where(Item.price.between(*fences))

    item_rows = (
        await db.execute(
            item_query
            .group_by(func.date(Item.created_at))
            .order_by(func.date(Item.created_at))
        )
    ).all()
    if item_rows:
        return [
            PriceTrendStat(
                bucket_ts=row.bucket_ts,
                avg_price=round(float(row.avg_price or 0)),
                items_num=int(row.items_num or 0),
            )
            for row in item_rows
        ]
    return stats


async def snapshot_price_stats(db: AsyncSession) -> int:
    """활성 매물을 (sku, emd)별로 집계해 price_stats에 당일 스냅샷을 upsert.

    price_stats를 채우는 유일한 경로. 크롤러 전체 실행 뒤에 호출되며,
    같은 날 재실행하면 해당 버킷을 덮어쓴다(멱등). emd_id가 없는 매물은
    PK 제약(sku, emd, bucket) 때문에 스냅샷에서 제외된다.
    """
    from sqlalchemy.dialects.mysql import insert as mysql_insert

    bucket = datetime.combine(datetime.now(timezone.utc).date(), time.min)
    sku_ids = (
        await db.execute(
            select(Item.sku_id)
            .where(Item.status == ItemStatus.active, Item.sku_id.is_not(None))
            .distinct()
        )
    ).scalars().all()

    written = 0
    for sku_id in sku_ids:
        agg = select(
            Item.emd_id,
            func.count(Item.item_id).label("cnt"),
            func.sum(Item.price).label("total"),
            func.avg(Item.price).label("avg"),
            func.min(Item.price).label("min"),
            func.max(Item.price).label("max"),
        ).where(
            Item.sku_id == sku_id,
            Item.status == ItemStatus.active,
            Item.emd_id.is_not(None),
        )
        fences = await get_price_fences(db, sku_id)
        if fences:
            agg = agg.where(Item.price.between(*fences))

        rows = (await db.execute(agg.group_by(Item.emd_id))).all()
        for row in rows:
            stmt = mysql_insert(PriceStats).values(
                sku_id=sku_id,
                emd_id=row.emd_id,
                bucket_ts=bucket,
                items_num=int(row.cnt),
                sum_price=int(row.total),
                avg_price=round(float(row.avg), 2),
                min_price=int(row.min),
                max_price=int(row.max),
            )
            stmt = stmt.on_duplicate_key_update(
                items_num=stmt.inserted.items_num,
                sum_price=stmt.inserted.sum_price,
                avg_price=stmt.inserted.avg_price,
                min_price=stmt.inserted.min_price,
                max_price=stmt.inserted.max_price,
            )
            await db.execute(stmt)
            written += 1

    await db.commit()
    return written
