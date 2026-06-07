from datetime import datetime

from pydantic import BaseModel


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
