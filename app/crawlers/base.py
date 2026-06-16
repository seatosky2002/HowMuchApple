import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawlers.targets import CRAWL_TARGETS, CrawlTarget
from app.db.models.category import Category
from app.db.models.crawler import CrawlerLog
from app.db.models.item import Item, ItemStatus
from app.services.region_matcher import resolve_region_id

logger = logging.getLogger(__name__)
INVALID_TEXT_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class CrawledItem:
    __slots__ = (
        "title",
        "price",
        "url",
        "external_id",
        "source",
        "region_name",
        "sku_id",
        "category_id",
        "target_category",
        "target_model",
        "search_keyword",
    )

    def __init__(
        self,
        title: str,
        price: int,
        url: str,
        external_id: str,
        source: str,
        region_name: str = "",
        sku_id: int | None = None,
        category_id: int | None = None,
        target_category: str = "",
        target_model: str = "",
        search_keyword: str = "",
    ):
        self.title = title
        self.price = price
        self.url = url
        self.external_id = external_id
        self.source = source
        self.region_name = region_name
        self.sku_id = sku_id
        self.category_id = category_id
        self.target_category = target_category
        self.target_model = target_model
        self.search_keyword = search_keyword


class BaseCrawler(ABC):
    platform: str = ""

    def __init__(self, targets: Iterable[CrawlTarget] | None = None):
        self.targets = tuple(targets or CRAWL_TARGETS)
        self._category_id_cache: dict[str, int | None] = {}

    @abstractmethod
    async def crawl(self) -> list[CrawledItem]:
        """플랫폼에서 매물 목록을 크롤링해 반환."""

    async def run(self, db: AsyncSession) -> int:
        log = CrawlerLog(platform=self.platform, status="running", started_at=datetime.now(timezone.utc))
        db.add(log)
        await db.commit()

        start = datetime.now(timezone.utc)
        try:
            items = await self.crawl()
            count = await self._upsert(db, items)
            elapsed = int((datetime.now(timezone.utc) - start).total_seconds())

            log.status = "success"
            log.items_upserted = count
            log.duration_sec = elapsed
            log.finished_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info("[%s] 완료 — %d개 upsert, %ds", self.platform, count, elapsed)
            return count
        except Exception as e:
            await db.rollback()
            elapsed = int((datetime.now(timezone.utc) - start).total_seconds())
            log.status = "fail"
            log.error = str(e)[:500]
            log.duration_sec = elapsed
            log.finished_at = datetime.now(timezone.utc)
            await db.commit()
            logger.error("[%s] 실패: %s", self.platform, e)
            raise

    async def _upsert(self, db: AsyncSession, items: list[CrawledItem]) -> int:
        count = 0
        for crawled in items:
            title = _db_safe_text(crawled.title)
            url = _db_safe_text(crawled.url)
            external_id = _db_safe_text(crawled.external_id)
            if not title or not url or not external_id:
                continue
            region_id = await self._resolve_region(db, _db_safe_text(crawled.region_name))
            category_id = crawled.category_id
            if category_id is None and crawled.target_category:
                category_id = await self._resolve_category_id(db, crawled.target_category)

            result = await db.execute(
                select(Item).where(Item.source == self.platform, Item.external_id == external_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.price = crawled.price
                existing.title = title
                existing.status = ItemStatus.active
                existing.url = url
                if region_id is not None:
                    existing.region_id = region_id
                if category_id is not None:
                    existing.category_id = category_id
            else:
                new_item = Item(
                    sku_id=crawled.sku_id,
                    region_id=region_id,
                    category_id=category_id,
                    title=title,
                    price=crawled.price,
                    url=url,
                    source=self.platform,
                    external_id=external_id,
                )
                db.add(new_item)
                count += 1

        await db.commit()
        return count

    async def _resolve_region(self, db: AsyncSession, region_text: str) -> int | None:
        return await resolve_region_id(db, region_text)

    async def _resolve_category_id(self, db: AsyncSession, category_name: str) -> int | None:
        if category_name in self._category_id_cache:
            return self._category_id_cache[category_name]

        result = await db.execute(select(Category.category_id).where(Category.name == category_name))
        category_id = result.scalar_one_or_none()
        self._category_id_cache[category_name] = category_id
        return category_id


async def run_all_crawlers(db: AsyncSession) -> None:
    from app.crawlers.daangn import DaangnCrawler
    from app.crawlers.bunjang import BunjangCrawler
    from app.crawlers.joongna import JoognaCrawler

    for crawler_cls in (DaangnCrawler, BunjangCrawler, JoognaCrawler):
        try:
            await crawler_cls().run(db)
        except Exception as e:
            logger.error("크롤러 %s 실패 (계속 진행): %s", crawler_cls.platform, e)


async def run_crawler_by_platform(platform: str, db: AsyncSession) -> None:
    from app.crawlers.daangn import DaangnCrawler
    from app.crawlers.bunjang import BunjangCrawler
    from app.crawlers.joongna import JoognaCrawler

    mapping = {
        "daangn": DaangnCrawler,
        "bunjang": BunjangCrawler,
        "joongna": JoognaCrawler,
    }
    cls = mapping.get(platform)
    if cls:
        await cls().run(db)


def _db_safe_text(value: str | None) -> str:
    if value is None:
        return ""
    return INVALID_TEXT_RE.sub("", str(value)).strip()
