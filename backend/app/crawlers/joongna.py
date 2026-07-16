import asyncio
import logging

import httpx

from app.crawlers.base import BaseCrawler, CrawledItem
from app.crawlers.filters import matches_target_listing

logger = logging.getLogger(__name__)

# 중고나라 웹 검색은 내부 API(search-api)가 처리한다. 이 API는 전체 결과를
# 페이지네이션으로 끝까지 내어주고, 매물마다 판매자 지역(locationNames)이 붙어
# 나오므로 Playwright 스크롤·상세페이지 지역 조회 없이 전량 수집이 가능하다.
# 지역 지정 검색(locationFilter)은 앱 전용이라 웹에선 쓸 수 없다.
# 조사 기록: docs/joongna_crawling_method.md
SEARCH_API = "https://search-api.joongna.com/v3/search/all"
PRODUCT_URL = "https://web.joongna.com/product/{seq}"
PAGE_SIZE = 50
MAX_PAGES_PER_KEYWORD = 40
EMPTY_PAGE_STOP = 2  # 신규 매물이 안 나오는 페이지가 연속 N번이면 키워드 종료
CRAWL_CONCURRENCY = 4  # 동시에 진행하는 타겟 수
FETCH_DELAY_S = 0.3
RETRY_BACKOFF_S = 10
MAX_RETRY = 3
FETCH_TIMEOUT_S = 25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Origin": "https://web.joongna.com",
    "Referer": "https://web.joongna.com/",
}


class JoognaCrawler(BaseCrawler):
    platform = "joongna"

    async def crawl(self) -> list[CrawledItem]:
        results: list[CrawledItem] = []
        seen_external_ids: set[str] = set()
        semaphore = asyncio.Semaphore(CRAWL_CONCURRENCY)

        async with httpx.AsyncClient(headers=HEADERS, timeout=FETCH_TIMEOUT_S) as client:
            await asyncio.gather(*[
                self._crawl_target(client, semaphore, target, seen_external_ids, results)
                for target in self.targets
            ])

        logger.info("[joongna] %d개 수집", len(results))
        return results

    async def _crawl_target(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        target,
        seen_external_ids: set[str],
        results: list[CrawledItem],
    ) -> None:
        async with semaphore:
            # 같은 매물이 타겟 내 여러 키워드에 걸려도 한 번만 처리
            processed_seqs: set[int] = set()
            for keyword in target.keywords:
                if self._is_full(results):
                    return
                await self._crawl_keyword(
                    client, target, keyword, processed_seqs, seen_external_ids, results
                )

    async def _crawl_keyword(
        self,
        client: httpx.AsyncClient,
        target,
        keyword: str,
        processed_seqs: set[int],
        seen_external_ids: set[str],
        results: list[CrawledItem],
    ) -> None:
        empty_pages = 0
        for page in range(MAX_PAGES_PER_KEYWORD):
            items = await _fetch_page(client, keyword, page)
            if items is None:
                logger.warning("joongna 키워드 '%s' page=%d 조회 실패, 키워드 중단", keyword, page)
                return

            new_count = 0
            for item in items:
                seq = item.get("seq")
                if not seq or seq in processed_seqs:
                    continue
                processed_seqs.add(seq)
                new_count += 1

                title = (item.get("title") or "").strip()
                price = item.get("price") or 0
                if price <= 0 or not matches_target_listing(title, price, target):
                    continue

                external_id = f"joongna_{seq}"
                if external_id in seen_external_ids:
                    continue
                if self._is_full(results):
                    return
                seen_external_ids.add(external_id)

                locations = item.get("locationNames") or []
                results.append(CrawledItem(
                    title=title,
                    price=price,
                    url=PRODUCT_URL.format(seq=seq),
                    external_id=external_id,
                    source="joongna",
                    region_name=locations[0] if locations else "",
                    target_category=target.category,
                    target_model=target.model,
                    search_keyword=keyword,
                ))
                if self._is_full(results):
                    return

            if new_count == 0:
                empty_pages += 1
                if empty_pages >= EMPTY_PAGE_STOP:
                    return
            else:
                empty_pages = 0
            await asyncio.sleep(FETCH_DELAY_S)

    def _is_full(self, results: list[CrawledItem]) -> bool:
        return self.max_items is not None and len(results) >= self.max_items


def _search_body(keyword: str, page: int) -> dict:
    return {
        "osType": 2,
        "firstQuantity": PAGE_SIZE,
        "quantity": PAGE_SIZE,
        "jnPayYn": "ALL",
        "categoryFilter": [{"categoryDepth": 0, "categorySeq": 0}],
        "priceFilter": {"minPrice": 0, "maxPrice": 100000000},
        "sort": "RECENT_SORT",
        "saleYn": "SALE_N",
        "parcelFeeYn": "ALL",
        "page": page,
        "searchWord": keyword,
        "adjustSearchKeyword": True,
        "keywordSource": "INPUT_KEYWORD",
        "registPeriod": "ALL",
    }


async def _fetch_page(client: httpx.AsyncClient, keyword: str, page: int) -> list[dict] | None:
    for attempt in range(MAX_RETRY + 1):
        try:
            response = await client.post(SEARCH_API, json=_search_body(keyword, page))
            if response.status_code in (429, 500, 502, 503):
                await asyncio.sleep(RETRY_BACKOFF_S * (attempt + 1))
                continue
            response.raise_for_status()
            data = response.json().get("data", {})
            return [i for i in data.get("items", []) if i.get("objectType") == "product"]
        except Exception as e:
            if attempt == MAX_RETRY:
                logger.debug("joongna 검색 실패 (%s, page=%d): %s", keyword, page, e)
                return None
            await asyncio.sleep(3)
    return None
