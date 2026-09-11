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


class SoldPriceSummary(BaseModel):
    """성사 거래가 — 판매완료로 바뀐 매물의 가격 분포.

    실거래 금액이 아니라 판매완료 직전의 마지막 게시 가격이므로 실거래가의
    상한으로 봐야 한다. by_source는 표본 출처를 화면에 정직하게 보여주기 위한 것.
    """

    avg_price: int
    median_price: int
    min_price: int
    max_price: int
    listing_count: int
    by_source: dict[str, int]
    # 최근 며칠간 거래완료로 관측된 매물만 집계했는지
    window_days: int


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
    # 성사 거래가 (표본이 없으면 None)
    sold_price: SoldPriceSummary | None = None


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
