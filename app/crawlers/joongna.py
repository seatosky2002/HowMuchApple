import asyncio
import logging
import re
from urllib.parse import quote

import httpx
from playwright.async_api import async_playwright

from app.crawlers.base import BaseCrawler, CrawledItem
from app.services.region_matcher import region_text_from_dong_code

logger = logging.getLogger(__name__)

KEYWORDS = ["아이폰", "아이패드", "맥북", "애플워치", "에어팟"]


class JoognaCrawler(BaseCrawler):
    platform = "joongna"

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
                        f"https://web.joongna.com/search/{quote(keyword)}",
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    await page.wait_for_timeout(5000)

                    listings = await page.locator('a[href*="/product/"]').evaluate_all(
                        """
                        els => els
                          .map(a => ({
                            href: a.href,
                            text: (a.innerText || a.textContent || "").trim().replace(/\\s+/g, " ")
                          }))
                          .filter(x => /\\/product\\/\\d+/.test(x.href) && x.text)
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

                            title, price = _parse_listing_text(text)
                            if price <= 0:
                                continue

                            normalized.append((title, price, href, external_id))
                            if len(normalized) >= 30:
                                break
                        except Exception as e:
                            logger.debug("joongna 아이템 파싱 오류: %s", e)

                    detail_regions = await _fetch_detail_regions(normalized)

                    for title, price, url, external_id in normalized:
                        try:
                            results.append(CrawledItem(
                                title=title,
                                price=price,
                                url=url,
                                external_id=f"joongna_{external_id}",
                                source="joongna",
                                region_name=detail_regions.get(external_id, ""),
                            ))
                        except Exception as e:
                            logger.debug("joongna 아이템 파싱 오류: %s", e)

                    await asyncio.sleep(2.0)
                except Exception as e:
                    logger.warning("joongna 키워드 '%s' 크롤링 실패: %s", keyword, e)

            await browser.close()

        logger.info("[joongna] %d개 수집", len(results))
        return results


def _parse_listing_text(text: str) -> tuple[str, int]:
    match = re.search(r"(.+?)\s+(\d[\d,]*)\s+원\b", text)
    if match:
        return match.group(1).strip(), _parse_price(match.group(2))
    if "무료나눔" in text:
        return text.split("무료나눔", 1)[0].strip(), 0
    return text.strip(), 0


def _parse_price(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return 0
    price = int(digits)
    if price < 1000:
        price *= 10000
    return price


async def _fetch_detail_regions(items: list[tuple[str, int, str, str]]) -> dict[str, str]:
    semaphore = asyncio.Semaphore(8)

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, timeout=20) as client:
        pairs = await asyncio.gather(
            *[_fetch_detail_region(client, semaphore, external_id) for _, _, _, external_id in items]
        )
    return {external_id: region for external_id, region in pairs}


async def _fetch_detail_region(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    external_id: str,
) -> tuple[str, str]:
    async with semaphore:
        try:
            response = await client.get(f"https://web.joongna.com/product/{external_id}")
            response.raise_for_status()
            return external_id, _extract_region_from_detail_html(response.text)
        except Exception as e:
            logger.debug("joongna 상세 위치 조회 실패 (%s): %s", external_id, e)
            return external_id, ""


def _extract_region_from_detail_html(html: str) -> str:
    location_match = re.search(r'\\"locationName\\":\\"([^\\"]+)', html)
    code_match = re.search(r'\\"dongCode\\":\\"([^\\"]+)', html)
    if location_match:
        dong_code = code_match.group(1) if code_match else None
        return region_text_from_dong_code(location_match.group(1), dong_code)

    address_match = re.search(
        r"(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)\s+"
        r"[^\s]{1,12}(?:시|군|구)\s+[^\s]{1,12}(?:동|읍|면|가)",
        html,
    )
    return address_match.group(0) if address_match else ""
