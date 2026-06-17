from datetime import datetime

from pydantic import BaseModel


class AttributeInput(BaseModel):
    attribute_id: int
    option_id: int


class SKUResolveRequest(BaseModel):
    category_id: int
    attributes: list[AttributeInput]


class SKUResolveResponse(BaseModel):
    sku_id: int
    category: str
    label: str
    fingerprint: str


class PriceSummary(BaseModel):
    avg_price: float
    min_price: int
    max_price: int
    listing_count: int
    updated_at: datetime | None


class AttributeValue(BaseModel):
    code: str
    label: str
    value: str


class SKUDetailResponse(BaseModel):
    sku_id: int
    category: str
    label: str
    attributes: list[AttributeValue]
    price_summary: PriceSummary


class PriceTrendPoint(BaseModel):
    bucket_ts: str
    avg_price: float
    listing_count: int


class PriceTrendResponse(BaseModel):
    sku_id: int
    region: str
    period: str
    change_rate: float
    chart_data: list[PriceTrendPoint]


class RegionPriceItem(BaseModel):
    sgg_id: int | None
    emd_id: int | None
    name: str
    avg_price: float
    listing_count: int


class RegionPricesResponse(BaseModel):
    sku_id: int
    level: str
    regions: list[RegionPriceItem]
