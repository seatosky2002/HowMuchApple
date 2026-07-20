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
from app.services.region_matcher import parse_region_parts, resolve_emd_id

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
        "dong_code",
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
        dong_code: str | None = None,
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
        self.dong_code = dong_code
        self.sku_id = sku_id
        self.category_id = category_id
        self.target_category = target_category
        self.target_model = target_model
        self.search_keyword = search_keyword


class BaseCrawler(ABC):
    platform: str = ""
    default_items_per_target: int = 30

    def __init__(self, targets: Iterable[CrawlTarget] | None = None, max_items: int | None = None):
        self.targets = tuple(targets or CRAWL_TARGETS)
        self.max_items = max_items
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
        from app.services.sku_assigner import SkuAssigner

        count = 0
        assigner = SkuAssigner()
        await assigner.load(db)
        for crawled in items:
            title = _db_safe_text(crawled.title)
            url = _db_safe_text(crawled.url)
            external_id = _db_safe_text(crawled.external_id)
            if not title or not url or not external_id:
                continue
            region_text = _db_safe_text(crawled.region_name)
            dong_code = _db_safe_text(crawled.dong_code)
            search_keyword = _db_safe_text(crawled.search_keyword)
            region_sgg, region_emd = parse_region_parts(region_text)
            emd_id = await self._resolve_region(db, region_text)
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
                existing.region_text = region_text or None
                existing.region_sgg = region_sgg
                existing.region_emd = region_emd
                existing.search_keyword = search_keyword or None
                if dong_code:
                    existing.dong_code = dong_code
                if emd_id is not None:
                    existing.emd_id = emd_id
                if category_id is not None:
                    existing.category_id = category_id
                item_row = existing
            else:
                new_item = Item(
                    sku_id=crawled.sku_id,
                    emd_id=emd_id,
                    category_id=category_id,
                    region_text=region_text or None,
                    region_sgg=region_sgg,
                    region_emd=region_emd,
                    dong_code=dong_code or None,
                    search_keyword=search_keyword or None,
                    title=title,
                    price=crawled.price,
                    url=url,
                    source=self.platform,
                    external_id=external_id,
                )
                db.add(new_item)
                count += 1
                item_row = new_item

            await db.flush()  # 신규 item_id 확보 (속성 적재에 필요)
            await assigner.assign(db, item_row)

        await db.commit()
        return count

    async def _resolve_region(self, db: AsyncSession, region_text: str) -> int | None:
        return await resolve_emd_id(db, region_text)

    async def _resolve_category_id(self, db: AsyncSession, category_name: str) -> int | None:
        if category_name in self._category_id_cache:
            return self._category_id_cache[category_name]

        result = await db.execute(select(Category.category_id).where(Category.name == category_name))
        category_id = result.scalar_one_or_none()
        self._category_id_cache[category_name] = category_id
        return category_id

    def _remaining_capacity(self, current_count: int) -> int | None:
        if self.max_items is None:
            return None
        return max(self.max_items - current_count, 0)

    def _target_capacity(self, current_count: int) -> int:
        remaining = self._remaining_capacity(current_count)
        if remaining is None:
            return self.default_items_per_target
        if len(self.targets) == 1:
            return remaining
        return min(self.default_items_per_target, remaining)


async def run_all_crawlers(db: AsyncSession) -> None:
    from app.crawlers.daangn import DaangnCrawler
    from app.crawlers.bunjang import BunjangCrawler
    from app.crawlers.joongna import JoognaCrawler

    for crawler_cls in (DaangnCrawler, BunjangCrawler, JoognaCrawler):
        try:
            await crawler_cls().run(db)
        except Exception as e:
            logger.error("크롤러 %s 실패 (계속 진행): %s", crawler_cls.platform, e)

    await _snapshot_price_stats(db)


async def _snapshot_price_stats(db: AsyncSession) -> None:
    from app.services.sku import snapshot_price_stats

    try:
        written = await snapshot_price_stats(db)
        logger.info("price_stats 일별 스냅샷 %d행 적재", written)
    except Exception as e:
        await db.rollback()
        logger.error("price_stats 스냅샷 실패: %s", e)


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
        await _snapshot_price_stats(db)


def _db_safe_text(value: str | None) -> str:
    if value is None:
        return ""
    return INVALID_TEXT_RE.sub("", str(value)).strip()
