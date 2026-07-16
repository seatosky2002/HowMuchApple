import asyncio
import hashlib
import logging
import re
from urllib.parse import quote, urlparse

import httpx

from app.crawlers.base import BaseCrawler, CrawledItem
from app.crawlers.daangn_regions import DAANGN_ANCHORS
from app.crawlers.filters import matches_target_listing

logger = logging.getLogger(__name__)

# 당근 웹 검색은 SSR이라 첫 페이지 HTML에 매물이 들어있다. Playwright 없이 httpx로
# 지역 지정 검색(?in=<동>-<id>&search=<키워드>)을 받아 파싱한다. 지역 지정을 안 하면
# 서버 기본 동네(신림동)만 잡히므로, 서울·경기 앵커 지역을 순회해 커버리지를 넓힌다.
BASE_URL = "https://www.daangn.com/kr/buy-sell/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
# 요청이 몰리면 당근이 429로 막으므로 동시성·간격을 보수적으로 둔다.
FETCH_CONCURRENCY = 4
FETCH_DELAY_S = 0.3
FETCH_429_BACKOFF_S = 10
FETCH_TIMEOUT_S = 20

_ANCHOR_RE = re.compile(r'<a[^>]+href="(/kr/buy-sell/[^"]+)"[^>]*>(.*?)</a>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")


class DaangnCrawler(BaseCrawler):
    platform = "daangn"

    async def crawl(self) -> list[CrawledItem]:
        results: list[CrawledItem] = []
        seen_external_ids: set[str] = set()
        semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)

        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=FETCH_TIMEOUT_S,
            follow_redirects=True,
        ) as client:
            tasks = [
                self._fetch_region_target(client, semaphore, region, target)
                for region in DAANGN_ANCHORS
                for target in self.targets
            ]
            for coro in asyncio.as_completed(tasks):
                listings = await coro
                for title, price, url, external_id, region, target in listings:
                    if external_id in seen_external_ids:
                        continue
                    if self.max_items is not None and len(results) >= self.max_items:
                        break
                    seen_external_ids.add(external_id)
                    results.append(CrawledItem(
                        title=title,
                        price=price,
                        url=url,
                        external_id=f"daangn_{external_id}",
                        source="daangn",
                        region_name=region,
                        target_category=target.category,
                        target_model=target.model,
                        search_keyword=target.primary_keyword,
                    ))

        logger.info("[daangn] %d개 수집 (앵커 %d곳)", len(results), len(DAANGN_ANCHORS))
        return results

    async def _fetch_region_target(self, client, semaphore, region: str, target):
        keyword = target.primary_keyword
        url = f"{BASE_URL}?in={quote(region)}&search={quote(keyword)}"
        async with semaphore:
            try:
                response = await client.get(url)
                if response.status_code == 429:
                    await asyncio.sleep(FETCH_429_BACKOFF_S)
                    response = await client.get(url)
                response.raise_for_status()
                html = response.text
            except Exception as e:
                logger.debug("daangn 검색 실패 (%s / %s): %s", region, keyword, e)
                return []
            finally:
                await asyncio.sleep(FETCH_DELAY_S)

        anchor_dong = region.rsplit("-", 1)[0]
        out = []
        for href, text in _extract_cards(html):
            title, price, item_region = _parse_listing_text(text)
            if price <= 0:
                continue
            if not matches_target_listing(title, price, target):
                continue
            external_id = _extract_external_id(href)
            full_url = href if href.startswith("http") else f"https://www.daangn.com{href}"
            out.append((title, price, full_url, external_id, item_region or anchor_dong, target))
        return out


def _extract_cards(html: str) -> list[tuple[str, str]]:
    cards = []
    for href, inner in _ANCHOR_RE.findall(html):
        if "/kr/buy-sell/s/" in href:
            continue
        text = re.sub(r"\s+", " ", _TAG_RE.sub(" ", inner)).strip()
        if text:
            cards.append((href, text))
    return cards


def _parse_listing_text(text: str) -> tuple[str, int, str]:
    match = re.search(r"(나눔|\d[\d,]*원)", text)
    if not match:
        return text.strip(), 0, ""

    title = text[:match.start()].strip()
    price = _parse_price(match.group(1))
    after_price = text[match.end():].strip()
    region = after_price.split("·", 1)[0].strip() if after_price else ""
    return title, price, region


def _extract_external_id(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    token = slug.rsplit("-", 1)[-1]
    if re.fullmatch(r"[a-zA-Z0-9]{8,32}", token):
        return token
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def _parse_price(text: str) -> int:
    if "나눔" in text:
        return 0
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return 0
    price = int(digits)
    if price < 1000:
        price *= 10000
    return price
