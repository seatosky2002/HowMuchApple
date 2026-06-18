from pydantic import BaseModel

from app.db.models.category import AttributeDatatype


class CategoryItem(BaseModel):
    category_id: int
    name: str
    model_config = {"from_attributes": True}


class CategoryListResponse(BaseModel):
    categories: list[CategoryItem]


class AttributeOptionItem(BaseModel):
    option_id: int
    value: str
    sort_order: int
    model_config = {"from_attributes": True}


class AttributeDetail(BaseModel):
    attribute_id: int
    code: str
    label: str
    datatype: AttributeDatatype
    unit: str | None
    is_required: bool
    display_group: str | None
    sort_order: int
    options: list[AttributeOptionItem]
    model_config = {"from_attributes": True}


class CategoryAttributesResponse(BaseModel):
    category_id: int
    name: str
    attributes: list[AttributeDetail]
