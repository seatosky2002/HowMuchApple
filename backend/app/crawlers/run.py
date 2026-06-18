import argparse
import asyncio
import logging

from app.crawlers.base import BaseCrawler
from app.crawlers.bunjang import BunjangCrawler
from app.crawlers.daangn import DaangnCrawler
from app.crawlers.joongna import JoognaCrawler
from app.crawlers.targets import CRAWL_TARGETS, CrawlTarget, target_counts_by_category, targets_for_category
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

CRAWLERS: dict[str, type[BaseCrawler]] = {
    "daangn": DaangnCrawler,
    "bunjang": BunjangCrawler,
    "joongna": JoognaCrawler,
}


def _select_targets(category: str | None, limit: int | None) -> tuple[CrawlTarget, ...]:
    targets = targets_for_category(category) if category else CRAWL_TARGETS
    return targets[:limit] if limit else targets


async def run_crawlers(platform: str, targets: tuple[CrawlTarget, ...], max_items: int | None = None) -> dict[str, int]:
    platforms = tuple(CRAWLERS) if platform == "all" else (platform,)
    counts: dict[str, int] = {}

    async with AsyncSessionLocal() as db:
        for platform_name in platforms:
            crawler = CRAWLERS[platform_name](targets=targets, max_items=max_items)
            counts[platform_name] = await crawler.run(db)

    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HowMuch crawlers with 2022+ Apple crawl targets.")
    parser.add_argument("--platform", choices=(*CRAWLERS.keys(), "all"), default="all")
    parser.add_argument("--category", choices=tuple(target_counts_by_category().keys()))
    parser.add_argument("--limit-targets", type=int, default=None)
    parser.add_argument("--limit-items", type=int, default=None)
    return parser.parse_args()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    args = parse_args()
    targets = _select_targets(args.category, args.limit_targets)
    logger.info(
        "크롤링 시작 — platform=%s, targets=%d, limit_items=%s",
        args.platform,
        len(targets),
        args.limit_items,
    )
    counts = await run_crawlers(args.platform, targets, max_items=args.limit_items)
    logger.info("크롤링 완료 — %s", counts)


if __name__ == "__main__":
    asyncio.run(main())
