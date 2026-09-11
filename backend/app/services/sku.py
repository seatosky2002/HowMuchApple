from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequest, NotFound
from app.db.models.category import Category, Attribute, AttributeOption, CategoryAttribute
from app.db.models.item import LISTED_STATUSES, Item, ItemStatus
from app.db.models.sku import SKU, SKUAttribute, PriceStats

# price_stats에서 "지역 미상"을 담는 예약 emd_id (마이그레이션 20260907_0002)
UNKNOWN_EMD_ID = 0
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

    # 존재하지 않는 조합(예: M5 Pro + 16GB) 검색은 유령 SKU를 만들지 않고 막는다
    from app.services.config_matrix import is_valid_config

    selected: dict[str, str] = {}
    for attr_id, opt_id in sorted_pairs:
        attr = await db.get(Attribute, attr_id)
        opt = await db.get(AttributeOption, opt_id)
        if attr and opt:
            selected[attr.code] = opt.value
    if not is_valid_config(category.name, selected):
        raise BadRequest("해당 모델에 존재하지 않는 사양 조합입니다. 용량·메모리를 다시 선택해주세요.")

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
    db: AsyncSession,
    sku_id: int,
    emd_id: int | None = None,
    statuses: tuple[ItemStatus, ...] = LISTED_STATUSES,
) -> tuple[int, int] | None:
    """매물 가격의 IQR 펜스(Q1-1.5·IQR, Q3+1.5·IQR).

    내구제·계정거래류 비매물성 글(예: 17e 256GB에 16만원)이 제목 필터를 뚫고
    들어와 평균/최저가를 왜곡하므로, 시세 집계에서는 펜스 밖 가격을 제외한다.
    표본 5개 미만이면 판단 불가로 None(필터 없음).

    statuses로 대상을 바꿀 수 있다 — 성사가는 sold 매물끼리 펜스를 잡아야
    호가 분포에 끌려가지 않는다.
    """
    query = select(Item.price).where(Item.sku_id == sku_id, Item.status.in_(statuses))
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


async def get_sold_price_summary(
    db: AsyncSession, sku_id: int, emd_id: int | None = None, days: int = 90
) -> dict | None:
    """성사 거래가 요약 — 판매완료로 바뀐 매물의 가격 분포.

    호가(=지금 올라와 있는 매물이 부르는 값)에는 끝까지 안 팔린 고가 매물이 계속
    남아 평균을 올린다. 반대로 적정가 매물은 금방 팔려 사라진다. 그래서 호가
    평균은 "안 팔리는 가격"이 과대 대표된다.

    주의: 여기서 얻는 값은 실거래 금액이 아니라 **판매완료로 바뀌기 직전의 마지막
    게시 가격**이다. 현장 네고는 반영되지 않으므로 실거래가의 상한으로 봐야 한다.
    그래도 "안 팔린 가격"이 걸러지므로 호가 평균보다 시장가에 가깝다.

    표본은 사실상 당근 위주다 — 당근만 검색 결과에 거래완료 매물이 노출되고
    번개·중고나라는 판매완료를 주지 않기 때문이다. 그래서 by_source를 함께
    돌려줘 화면이 표본 출처를 정직하게 보여줄 수 있게 한다.

    days로 최근 관측분만 본다. 성사 표본은 시간이 지나며 누적되는데 중고가는
    떨어지므로, 기간 제한이 없으면 과거 가격이 섞여 성사가가 현재 호가보다 높게
    나오기도 한다(실측 사례 있음). 다만 "팔린 시점"은 알 수 없고 **거래완료
    상태로 마지막 관측된 시점**(updated_at)이 기준이라는 한계가 있다.

    데이터가 없으면 None.
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = select(Item.price, Item.source).where(
        Item.sku_id == sku_id,
        Item.status == ItemStatus.sold,
        Item.updated_at >= cutoff,
    )
    if emd_id:
        query = query.where(Item.emd_id == emd_id)

    fences = await get_price_fences(db, sku_id, emd_id, statuses=(ItemStatus.sold,))
    if fences:
        query = query.where(Item.price.between(*fences))

    rows = (await db.execute(query)).all()
    if not rows:
        return None

    prices = sorted(int(r.price) for r in rows)
    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r.source] = by_source.get(r.source, 0) + 1

    return {
        "avg_price": round(sum(prices) / len(prices)),
        "median_price": int(_percentile(prices, 0.5)),
        "min_price": prices[0],
        "max_price": prices[-1],
        "listing_count": len(prices),
        "by_source": by_source,
        "window_days": days,
    }


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
    ).where(Item.sku_id == sku_id, Item.status.in_(LISTED_STATUSES))
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
        Item.status.in_(LISTED_STATUSES),
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
    같은 날 재실행하면 해당 버킷을 덮어쓴다(멱등).

    지역을 못 알아낸 매물(emd_id IS NULL)은 예약값 UNKNOWN_EMD_ID(0)로 모은다.
    전국 조회는 emd를 무시하고 합산하므로 그대로 반영되고, 지역별 조회는 실제
    emd_id를 지정하므로 섞이지 않는다. 예전에는 이 매물들을 버려서 전국 추이에서
    통째로 빠졌다(운영 실측 6,986건).
    """
    from sqlalchemy.dialects.mysql import insert as mysql_insert

    bucket = datetime.combine(datetime.now(timezone.utc).date(), time.min)
    sku_ids = (
        await db.execute(
            select(Item.sku_id)
            .where(Item.status.in_(LISTED_STATUSES), Item.sku_id.is_not(None))
            .distinct()
        )
    ).scalars().all()

    written = 0
    for sku_id in sku_ids:
        emd_bucket = func.coalesce(Item.emd_id, UNKNOWN_EMD_ID).label("emd_id")
        agg = select(
            emd_bucket,
            func.count(Item.item_id).label("cnt"),
            func.sum(Item.price).label("total"),
            func.avg(Item.price).label("avg"),
            func.min(Item.price).label("min"),
            func.max(Item.price).label("max"),
        ).where(
            Item.sku_id == sku_id,
            Item.status.in_(LISTED_STATUSES),
        )
        fences = await get_price_fences(db, sku_id)
        if fences:
            agg = agg.where(Item.price.between(*fences))

        rows = (await db.execute(agg.group_by(emd_bucket))).all()
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
