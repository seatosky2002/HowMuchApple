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
    # 변형 필터: variant_controller 속성(예: model)을 고르면
    # variants[모델값][속성 code]에 있는 옵션만 노출한다
    variant_controller: str | None = None
    variants: dict[str, dict[str, list[str]]] | None = None
