from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFound
from app.db.models.category import Category, CategoryAttribute
from app.db.session import get_db
from app.schemas.category import (
    AttributeDetail,
    AttributeOptionItem,
    CategoryAttributesResponse,
    CategoryItem,
    CategoryListResponse,
)

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=CategoryListResponse)
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).order_by(Category.category_id))
    cats = result.scalars().all()
    return CategoryListResponse(categories=[CategoryItem.model_validate(c) for c in cats])


@router.get("/{category_id}/attributes", response_model=CategoryAttributesResponse)
async def get_category_attributes(category_id: int, db: AsyncSession = Depends(get_db)):
    category = await db.get(Category, category_id)
    if not category:
        raise NotFound("카테고리를 찾을 수 없습니다.")

    result = await db.execute(
        select(CategoryAttribute)
        .where(CategoryAttribute.category_id == category_id)
        .options(
            selectinload(CategoryAttribute.attribute).selectinload(
                __import__("app.db.models.category", fromlist=["Attribute"]).Attribute.options
            )
        )
        .order_by(CategoryAttribute.sort_order)
    )
    cat_attrs = result.scalars().all()

    attributes = []
    for ca in cat_attrs:
        attr = ca.attribute
        options = [AttributeOptionItem.model_validate(o) for o in attr.options]
        attributes.append(
            AttributeDetail(
                attribute_id=attr.attribute_id,
                code=attr.code,
                label=attr.label,
                datatype=attr.datatype,
                unit=attr.unit,
                is_required=ca.is_required,
                display_group=ca.display_group,
                sort_order=ca.sort_order,
                options=options,
            )
        )

    return CategoryAttributesResponse(
        category_id=category.category_id,
        name=category.name,
        attributes=attributes,
    )
