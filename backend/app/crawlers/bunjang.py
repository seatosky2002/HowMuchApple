import asyncio
import logging

import httpx

from app.crawlers.base import BaseCrawler, CrawledItem
from app.crawlers.filters import matches_target_listing

logger = logging.getLogger(__name__)

# find_v2의 lat/lon/distance는 필터로 동작하지 않는다(무시됨). 대신 order=distance가
# 좌표 기준 거리순 '정렬'로 동작하므로, 서울시청을 중심으로 페이지를 넘기면
# 서울 → 경기 → 지방 → 위치없음 순으로 나온다. 서울/경기 매물이 안 나오는 지점에서
# 끊으면 지역 내 위치 등록 매물을 전량 수집한다. 중심점을 바꿔도 수집 집합은 동일함을
# 실측으로 확인했다 — 상세는 docs/bunjang_api_behavior.md 참조.
BUNJANG_API = "https://api.bunjang.co.kr/api/1/find_v2.json"
CENTER_LAT = "37.5665"  # 서울시청
CENTER_LON = "126.9780"
BUNJANG_PAGE_SIZE = 200  # API 허용 최대 (300은 400 에러)
MAX_BUNJANG_PAGES = 50  # 오프셋 10,000 미만까지만 접근 가능
STOP_AFTER_NO_REGION_PAGES = 2  # 서울/경기 0건 페이지 연속 N회면 키워드 종료
REQUEST_DELAY_S = 0.35
RETRY_429_BACKOFF_S = 30

_REGION_PREFIXES = ("서울", "경기")


class BunjangCrawler(BaseCrawler):
    platform = "bunjang"

    async def crawl(self) -> list[CrawledItem]:
        results: list[CrawledItem] = []
        seen_pids: set[str] = set()

        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://m.bunjang.co.kr/"},
            timeout=20,
        ) as client:
            for target in self.targets:
                for keyword in target.keywords:
                    try:
                        await self._crawl_keyword(client, keyword, target, seen_pids, results)
                    except Exception as e:
                        logger.warning("bunjang 키워드 '%s' 크롤링 실패: %s", keyword, e)
                    if self.max_items is not None and len(results) >= self.max_items:
                        logger.info("[bunjang] max_items(%d) 도달, 조기 종료", self.max_items)
                        return results

        logger.info("[bunjang] %d개 수집 (서울·경기)", len(results))
        return results

    async def _crawl_keyword(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        target,
        seen_pids: set[str],
        results: list[CrawledItem],
    ) -> None:
        no_region_streak = 0

        for page_num in range(MAX_BUNJANG_PAGES):
            data = await self._fetch_page(client, keyword, page_num)
            await asyncio.sleep(REQUEST_DELAY_S)
            if data is None:
                return
            items = data.get("list") or []
            if not items:
                return

            page_region_count = 0
            for item in items:
                location = (item.get("location") or "").strip()
                if not location.startswith(_REGION_PREFIXES):
                    continue
                page_region_count += 1
                self._append_item(item, location, keyword, target, seen_pids, results)
                if self.max_items is not None and len(results) >= self.max_items:
                    return

            if page_region_count == 0:
                no_region_streak += 1
                if no_region_streak >= STOP_AFTER_NO_REGION_PAGES:
                    return  # 거리순 정렬상 서울/경기 구간을 지나감
            else:
                no_region_streak = 0

    async def _fetch_page(
        self, client: httpx.AsyncClient, keyword: str, page_num: int
    ) -> dict | None:
        for attempt in range(3):
            resp = await client.get(
                BUNJANG_API,
                params={
                    "q": keyword,
                    "order": "distance",
                    "page": page_num,
                    "n": BUNJANG_PAGE_SIZE,
                    "lat": CENTER_LAT,
                    "lon": CENTER_LON,
                },
            )
            if resp.status_code == 429:
                wait = RETRY_429_BACKOFF_S * (attempt + 1)
                logger.warning("bunjang 429 — %ds 대기 후 재시도 (%s p%d)", wait, keyword, page_num)
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        return None

    def _append_item(
        self,
        item: dict,
        location: str,
        keyword: str,
        target,
        seen_pids: set[str],
        results: list[CrawledItem],
    ) -> None:
        try:
            pid = str(item.get("pid", ""))
            title = (item.get("name") or "").strip()
            price = int(item.get("price", 0))
        except (TypeError, ValueError):
            return
        if not pid or price <= 0 or pid in seen_pids:
            return
        if not matches_target_listing(title, price, target):
            return

        seen_pids.add(pid)
        results.append(CrawledItem(
            title=title,
            price=price,
            url=f"https://m.bunjang.co.kr/products/{pid}",
            external_id=f"bunjang_{pid}",
            source="bunjang",
            region_name=location,
            target_category=target.category,
            target_model=target.model,
            search_keyword=keyword,
        ))
