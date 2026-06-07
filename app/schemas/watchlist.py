from datetime import datetime

from pydantic import BaseModel, field_validator


class WatchlistCreateRequest(BaseModel):
    sku_id: int
    region_id: int | None = None
    max_price: int
    label: str | None = None
    alert_channels: list[str] = ["email"]

    @field_validator("max_price")
    @classmethod
    def positive_price(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_price는 양수여야 합니다.")
        return v

    @field_validator("alert_channels")
    @classmethod
    def valid_channels(cls, v: list[str]) -> list[str]:
        allowed = {"email", "sms"}
        invalid = set(v) - allowed
        if invalid:
            raise ValueError(f"유효하지 않은 채널: {invalid}")
        return v


class WatchlistUpdateRequest(BaseModel):
    max_price: int | None = None
    label: str | None = None
    alert_channels: list[str] | None = None

    @field_validator("max_price")
    @classmethod
    def positive_price(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("max_price는 양수여야 합니다.")
        return v


class LatestAlert(BaseModel):
    alert_id: int
    triggered_at: datetime
    is_read: bool


class WatchlistItem(BaseModel):
    watch_id: int
    sku_id: int
    label: str | None
    product: str
    spec_label: str
    region: dict | None
    max_price: int
    is_active: bool
    alert_channels: list[str]
    latest_alert: LatestAlert | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WatchlistResponse(BaseModel):
    watchlist: list[WatchlistItem]


class WatchlistDetailResponse(BaseModel):
    watch_id: int
    sku_id: int
    spec_label: str
    attributes: list[dict]
    region: dict | None
    max_price: int
    is_active: bool
    alert_channels: list[str]
    created_at: datetime
    updated_at: datetime


class ActiveToggleResponse(BaseModel):
    watch_id: int
    is_active: bool


class WatchlistAlertItem(BaseModel):
    alert_id: int
    message: str
    item_id: int | None
    listing_price: int | None
    is_read: bool
    triggered_at: datetime


class WatchlistAlertsResponse(BaseModel):
    watch_id: int
    total: int
    alerts: list[WatchlistAlertItem]
