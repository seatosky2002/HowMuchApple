from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.db.models.category import AttributeDatatype
from app.schemas.category import AttributeDetail


class AdminStatsResponse(BaseModel):
    users: dict
    listings: dict
    watchlists: dict
    alerts_sent_today: int


class CrawlerStatusItem(BaseModel):
    platform: str
    last_run_at: datetime | None
    status: str | None
    items_upserted: int
    duration_sec: int | None
    error: str | None


class CrawlerStatusResponse(BaseModel):
    crawlers: list[CrawlerStatusItem]


class TriggerCrawlerResponse(BaseModel):
    message: str
    job_id: str


class SchedulerJob(BaseModel):
    job_id: str
    name: str
    cron: str
    next_run_at: datetime | None
    status: str


class SchedulerJobsResponse(BaseModel):
    jobs: list[SchedulerJob]


class AdminUserItem(BaseModel):
    user_id: int
    email: str
    nickname: str
    is_email_verified: bool
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUsersResponse(BaseModel):
    total: int
    users: list[AdminUserItem]


class UserStatusUpdate(BaseModel):
    status: str
    reason: str | None = None


class AdminCategoryItem(BaseModel):
    category_id: int
    name: str
    attributes: list[AttributeDetail]


class AdminCategoriesResponse(BaseModel):
    categories: list[AdminCategoryItem]


class AdminAttributeOptionCreate(BaseModel):
    value: str
    sort_order: int = 0


class AdminCategoryAttributeCreate(BaseModel):
    attribute_id: int | None = None
    code: str | None = None
    label: str | None = None
    datatype: AttributeDatatype | None = None
    unit: str | None = None
    description: str | None = None
    is_required: bool = False
    display_group: str | None = None
    sort_order: int = 0
    options: list[AdminAttributeOptionCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_attribute_reference(self):
        if self.attribute_id is not None:
            return self
        missing = [
            field
            for field in ("code", "label", "datatype")
            if getattr(self, field) is None
        ]
        if missing:
            raise ValueError("attribute_id가 없으면 code, label, datatype이 필요합니다.")
        return self
