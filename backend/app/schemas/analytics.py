from datetime import datetime

from pydantic import BaseModel


class PriceTrendPoint(BaseModel):
    bucket_ts: str
    avg_price: float


class RegionalBreakdownItem(BaseModel):
    sgg: str
    emd: str
    avg_price: float
    listing_count: int


class AnalyticsSummaryResponse(BaseModel):
    sku_id: int
    label: str
    region: str
    summary: dict
    price_trend: dict
    regional_breakdown: list[RegionalBreakdownItem]


class ListingItem(BaseModel):
    item_id: int
    listing_price: int
    title: str
    sgg: str | None
    emd: str | None
    source: str
    source_url: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ListingsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    listings: list[ListingItem]


class TrendingItem(BaseModel):
    sku_id: int
    label: str
    avg_price: float
    change_rate: float
    direction: str


class TrendingResponse(BaseModel):
    trending: list[TrendingItem]


class PopularItem(BaseModel):
    sku_id: int
    label: str
    avg_price: float
    search_count: int


class PopularResponse(BaseModel):
    popular: list[PopularItem]


class PlatformPriceItem(BaseModel):
    source: str
    avg_price: float
    listing_count: int


class PlatformCompareResponse(BaseModel):
    sku_id: int
    platforms: list[PlatformPriceItem]
