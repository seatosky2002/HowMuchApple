import asyncio
from html import unescape
import logging
import re
from urllib.parse import quote

import httpx
from playwright.async_api import async_playwright

from app.crawlers.base import BaseCrawler, CrawledItem

logger = logging.getLogger(__name__)

KEYWORDS = [
    "아이폰", "아이패드", "맥북", "애플워치", "에어팟",
    "iPhone", "iPad", "MacBook", "Apple Watch", "AirPods",
]


class DaangnCrawler(BaseCrawler):
    platform = "daangn"

    async def crawl(self) -> list[CrawledItem]:
        results: list[CrawledItem] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await context.new_page()

            for keyword in KEYWORDS:
                try:
                    await page.goto(
                        f"https://www.daangn.com/kr/buy-sell/?search={quote(keyword)}",
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    await page.wait_for_timeout(5000)

                    listings = await page.locator('a[href*="/kr/buy-sell/"]').evaluate_all(
                        """
                        els => els
                          .map(a => ({
                            href: a.href,
                            text: (a.innerText || a.textContent || "").trim().replace(/\\s+/g, " ")
                          }))
                          .filter(x =>
                            x.href.includes("/kr/buy-sell/") &&
                            !x.href.includes("/kr/buy-sell/s/") &&
                            x.text
                          )
                        """
                    )

                    normalized = []
                    seen: set[str] = set()
                    for listing in listings:
                        try:
                            href = listing.get("href")
                            text = listing.get("text", "")
                            if not href or not text:
                                continue

                            external_id = href.rstrip("/").split("/")[-1]
                            if external_id in seen:
                                continue
                            seen.add(external_id)

                            title, price, region = _parse_listing_text(text)
                            if price <= 0:
                                continue

                            normalized.append((title, price, href, external_id, region))
                            if len(normalized) >= 30:
                                break
                        except Exception as e:
                            logger.debug("daangn 아이템 파싱 오류: %s", e)

                    detail_regions = await _fetch_detail_regions(normalized)

                    for title, price, href, external_id, region in normalized:
                        try:
                            results.append(CrawledItem(
                                title=title,
                                price=price,
                                url=href,
                                external_id=f"daangn_{external_id}",
                                source="daangn",
                                region_name=detail_regions.get(external_id) or region,
                            ))
                        except Exception as e:
                            logger.debug("daangn 아이템 파싱 오류: %s", e)

                    await asyncio.sleep(1.5)
                except Exception as e:
                    logger.warning("daangn 키워드 '%s' 크롤링 실패: %s", keyword, e)

            await browser.close()

        logger.info("[daangn] %d개 수집", len(results))
        return results


def _parse_listing_text(text: str) -> tuple[str, int, str]:
    match = re.search(r"(나눔|\d[\d,]*원)", text)
    if not match:
        return text.strip(), 0, ""

    title = text[:match.start()].strip()
    price = _parse_price(match.group(1))
    after_price = text[match.end():].strip()
    region = after_price.split("·", 1)[0].strip() if after_price else ""
    return title, price, region


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


async def _fetch_detail_regions(items: list[tuple[str, int, str, str, str]]) -> dict[str, str]:
    semaphore = asyncio.Semaphore(8)

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, timeout=20) as client:
        pairs = await asyncio.gather(
            *[_fetch_detail_region(client, semaphore, url, external_id) for _, _, url, external_id, _ in items]
        )
    return {external_id: region for external_id, region in pairs if region}


async def _fetch_detail_region(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
    external_id: str,
) -> tuple[str, str]:
    async with semaphore:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return external_id, _extract_region_from_detail_html(response.text)
        except Exception as e:
            logger.debug("daangn 상세 위치 조회 실패 (%s): %s", external_id, e)
            return external_id, ""


def _extract_region_from_detail_html(html: str) -> str:
    for match in re.finditer(r'<a[^>]+href="/kr/buy-sell/s/\?in=[^"]+"[^>]*>([^<]+)</a>', html):
        candidate = unescape(match.group(1)).strip()
        if _looks_like_region(candidate):
            return candidate

    match = re.search(
        r"(서울시|서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|"
        r"세종특별자치시|경기도|강원특별자치도|충청북도|충청남도|전북특별자치도|전라남도|"
        r"경상북도|경상남도|제주특별자치도)\s+"
        r"[^\s<]{1,12}(?:시|군|구)\s+[^\s<]{1,12}(?:동|읍|면|가)",
        html,
    )
    return unescape(match.group(0)).strip() if match else ""


def _looks_like_region(value: str) -> bool:
    return bool(
        re.search(
            r"(서울시|서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|"
            r"세종특별자치시|경기도|강원특별자치도|충청북도|충청남도|전북특별자치도|전라남도|"
            r"경상북도|경상남도|제주특별자치도)\s+.+(?:동|읍|면|가)$",
            value,
        )
    )
