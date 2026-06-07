from datetime import datetime

from pydantic import BaseModel


class AlertItemDetail(BaseModel):
    item_id: int
    listing_price: int
    source: str
    source_url: str


class AlertDetail(BaseModel):
    alert_id: int
    watch_id: int
    watch_label: str | None
    spec_label: str
    message: str
    item: AlertItemDetail | None
    is_read: bool
    triggered_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    total: int
    unread: int
    alerts: list[AlertDetail]


class UnreadCountResponse(BaseModel):
    unread: int


class BulkDeleteRequest(BaseModel):
    alert_ids: list[int] | None = None


class BulkDeleteResponse(BaseModel):
    deleted_count: int
