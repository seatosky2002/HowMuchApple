from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.sku import (
    PriceTrendResponse,
    RegionPricesResponse,
    SKUDetailResponse,
    SKUResolveRequest,
    SKUResolveResponse,
)
from app.services import sku as sku_service

router = APIRouter(prefix="/sku", tags=["SKU"])


@router.post("/resolve", response_model=SKUResolveResponse)
async def resolve_sku(body: SKUResolveRequest, db: AsyncSession = Depends(get_db)):
    sku = await sku_service.resolve_sku(db, body.category_id, body.attributes)
    label = await sku_service.build_sku_label(sku)
    return SKUResolveResponse(
        sku_id=sku.sku_id,
        category=sku.category.name if sku.category else "",
        label=label,
        fingerprint=sku.fingerprint,
    )


@router.get("/{sku_id}", response_model=SKUDetailResponse)
async def get_sku(sku_id: int, db: AsyncSession = Depends(get_db)):
    sku, price_summary = await sku_service.get_sku_with_price(db, sku_id)
    label = await sku_service.build_sku_label(sku)

    from app.schemas.sku import AttributeValue, PriceSummary
    attrs = []
    for sa in sorted(sku.attributes, key=lambda x: x.attribute_id):
        attrs.append(AttributeValue(
            code=sa.attribute.code,
            label=sa.attribute.label,
            value=sa.option.value if sa.option else sa.value_text or "",
        ))

    return SKUDetailResponse(
        sku_id=sku.sku_id,
        category=sku.category.name if sku.category else "",
        label=label,
        attributes=attrs,
        price_summary=PriceSummary(**price_summary),
    )


@router.get("/{sku_id}/price-trend", response_model=PriceTrendResponse)
async def get_price_trend(
    sku_id: int,
    region_id: int | None = Query(default=None),
    period: str = Query(default="4w", pattern="^(4w|8w|3m|6m|1y)$"),
    db: AsyncSession = Depends(get_db),
):
    stats = await sku_service.get_price_trend(db, sku_id, region_id, period)

    chart = [
        {"bucket_ts": s.bucket_ts.strftime("%Y-%m-%d"), "avg_price": float(s.avg_price), "listing_count": s.items_num}
        for s in stats
    ]
    change_rate = 0.0
    if len(chart) >= 2:
        first, last = chart[0]["avg_price"], chart[-1]["avg_price"]
        if first:
            change_rate = round((last - first) / first * 100, 1)

    from app.db.models.region import EMD, SGG
    region_name = "서울 전체"
    if region_id:
        emd = await db.get(EMD, region_id)
        if emd:
            sgg = await db.get(SGG, emd.sgg_id)
            region_name = f"{sgg.name} {emd.name}" if sgg else emd.name

    from app.schemas.sku import PriceTrendPoint
    return PriceTrendResponse(
        sku_id=sku_id,
        region=region_name,
        period=period,
        change_rate=change_rate,
        chart_data=[PriceTrendPoint(**p) for p in chart],
    )


@router.get("/{sku_id}/region-prices", response_model=RegionPricesResponse)
async def get_region_prices(
    sku_id: int,
    sd_id: int | None = Query(default=None),
    level: str = Query(default="sgg", pattern="^(sgg|emd)$"),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func, select
    from app.db.models.sku import PriceStats
    from app.db.models.region import EMD, SGG, SD

    if level == "sgg":
        query = (
            select(
                SGG.sgg_id,
                SGG.name,
                func.avg(PriceStats.avg_price).label("avg"),
                func.sum(PriceStats.items_num).label("cnt"),
            )
            .join(EMD, PriceStats.region_id == EMD.region_id)
            .join(SGG, EMD.sgg_id == SGG.sgg_id)
            .where(PriceStats.sku_id == sku_id)
            .group_by(SGG.sgg_id, SGG.name)
        )
        if sd_id:
            query = query.where(SGG.sd_id == sd_id)
        rows = (await db.execute(query)).all()
        regions = [
            {"sgg_id": r.sgg_id, "region_id": None, "name": r.name, "avg_price": float(r.avg), "listing_count": int(r.cnt)}
            for r in rows
        ]
    else:
        query = (
            select(
                EMD.region_id,
                EMD.name,
                func.avg(PriceStats.avg_price).label("avg"),
                func.sum(PriceStats.items_num).label("cnt"),
            )
            .join(EMD, PriceStats.region_id == EMD.region_id)
            .join(SGG, EMD.sgg_id == SGG.sgg_id)
            .where(PriceStats.sku_id == sku_id)
            .group_by(EMD.region_id, EMD.name)
        )
        if sd_id:
            query = query.where(SGG.sd_id == sd_id)
        rows = (await db.execute(query)).all()
        regions = [
            {"sgg_id": None, "region_id": r.region_id, "name": r.name, "avg_price": float(r.avg), "listing_count": int(r.cnt)}
            for r in rows
        ]

    from app.schemas.sku import RegionPriceItem
    return RegionPricesResponse(
        sku_id=sku_id,
        level=level,
        regions=[RegionPriceItem(**r) for r in regions],
    )
