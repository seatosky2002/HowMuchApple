from datetime import datetime

from pydantic import BaseModel


class PlatformStats(BaseModel):
    listing_count: int
    last_crawled_at: datetime | None


class ServiceStatsResponse(BaseModel):
    total_listings: int
    total_skus: int
    last_crawled_at: datetime | None
    platforms: dict[str, PlatformStats]


class AdminStatsResponse(BaseModel):
    users: dict
    listings: dict
    watchlists: dict
    alerts_sent_today: int
