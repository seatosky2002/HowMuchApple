from datetime import datetime

from pydantic import BaseModel


class RegionInfo(BaseModel):
    sgg: str | None
    emd: str | None
    dong_code: str | None = None


class ItemDetailResponse(BaseModel):
    item_id: int
    sku_id: int | None
    label: str
    title: str
    price: int
    status: str
    region: RegionInfo
    source: str
    source_url: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SimilarItem(BaseModel):
    item_id: int
    price: int
    sgg: str | None
    source: str
    source_url: str


class SimilarItemsResponse(BaseModel):
    sku_id: int
    items: list[SimilarItem]
