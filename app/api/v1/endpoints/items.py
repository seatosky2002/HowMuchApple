from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.db.models.item import Item, ItemStatus
from app.db.models.region import EMD, SGG
from app.db.models.sku import SKU, SKUAttribute
from app.db.session import get_db
from app.schemas.item import ItemDetailResponse, RegionInfo, SimilarItem, SimilarItemsResponse
from app.services.sku import build_sku_label

router = APIRouter(prefix="/items", tags=["Items"])


@router.get("/{item_id}", response_model=ItemDetailResponse)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(Item, item_id)
    if not item:
        raise NotFound("매물을 찾을 수 없습니다.")

    emd = await db.get(EMD, item.region_id) if item.region_id else None
    sgg = await db.get(SGG, emd.sgg_id) if emd else None
    sku = await db.get(SKU, item.sku_id) if item.sku_id else None
    label = ""
    if sku:
        from sqlalchemy.orm import selectinload
        sku = (await db.execute(
            select(SKU).where(SKU.sku_id == item.sku_id)
            .options(selectinload(SKU.attributes).selectinload(SKUAttribute.option))
        )).scalar_one_or_none()
        label = await build_sku_label(sku) if sku else ""

    return ItemDetailResponse(
        item_id=item.item_id,
        sku_id=item.sku_id,
        label=label,
        title=item.title,
        price=item.price,
        status=item.status.value,
        region=RegionInfo(sgg=sgg.name if sgg else item.region_sgg, emd=emd.name if emd else item.region_emd),
        source=item.source,
        source_url=item.url,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/{item_id}/similar", response_model=SimilarItemsResponse)
async def get_similar_items(
    item_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    sort: str = Query(default="price_asc", pattern="^(price_asc|price_desc|newest)$"),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Item, item_id)
    if not item or not item.sku_id:
        raise NotFound("매물을 찾을 수 없습니다.")

    sort_map = {
        "price_asc": Item.price.asc(),
        "price_desc": Item.price.desc(),
        "newest": Item.created_at.desc(),
    }
    result = await db.execute(
        select(Item)
        .where(Item.sku_id == item.sku_id, Item.item_id != item_id, Item.status == ItemStatus.active)
        .order_by(sort_map.get(sort, Item.price.asc()))
        .limit(limit)
    )
    items = result.scalars().all()

    similar = []
    for i in items:
        emd = await db.get(EMD, i.region_id) if i.region_id else None
        sgg = await db.get(SGG, emd.sgg_id) if emd else None
        similar.append(SimilarItem(
            item_id=i.item_id,
            price=i.price,
            sgg=sgg.name if sgg else i.region_sgg,
            source=i.source,
            source_url=i.url,
        ))

    return SimilarItemsResponse(sku_id=item.sku_id, items=similar)
