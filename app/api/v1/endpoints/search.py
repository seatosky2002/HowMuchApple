from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.sku import SKU, SKUAttribute
from app.db.session import get_db
from app.schemas.search import AutocompleteResponse, AutocompleteSuggestion
from app.services.sku import build_sku_label

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(
    q: str = Query(..., min_length=1),
    category_id: int | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    # Load SKUs with their option values and filter by label match
    query = (
        select(SKU)
        .options(
            selectinload(SKU.category),
            selectinload(SKU.attributes).selectinload(SKUAttribute.option),
        )
    )
    if category_id:
        query = query.where(SKU.category_id == category_id)

    all_skus = (await db.execute(query)).scalars().all()

    suggestions = []
    q_lower = q.lower()
    for sku in all_skus:
        label = await build_sku_label(sku)
        if q_lower in label.lower():
            suggestions.append(
                AutocompleteSuggestion(
                    sku_id=sku.sku_id,
                    label=label,
                    category=sku.category.name if sku.category else "",
                )
            )
        if len(suggestions) >= limit:
            break

    return AutocompleteResponse(suggestions=suggestions)
