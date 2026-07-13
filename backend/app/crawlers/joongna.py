import asyncio
import logging
import re
from html import unescape
from urllib.parse import quote

import httpx
from playwright.async_api import async_playwright

from app.crawlers.base import BaseCrawler, CrawledItem
from app.crawlers.filters import matches_target_listing
from app.services.region_matcher import region_text_from_dong_code

logger = logging.getLogger(__name__)
MAX_SCROLL_ROUNDS = 25
MAX_HTML_PAGES = 10
SCROLL_SETTLE_MS = 1200


class JoognaCrawler(BaseCrawler):
    platform = "joongna"

    async def crawl(self) -> list[CrawledItem]:
        results: list[CrawledItem] = []
        seen_external_ids: set[str] = set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await context.new_page()

            for target in self.targets:
                per_target_limit = self._target_capacity(len(results))
                if per_target_limit == 0:
                    break
                normalized = []
                processed_external_ids: set[str] = set()
                processed_html_external_ids: set[str] = set()

                for keyword in target.keywords:
                    if len(normalized) >= per_target_limit:
                        break
                    try:
                        await page.goto(
                            f"https://web.joongna.com/search/{quote(keyword)}",
                            wait_until="domcontentloaded",
                            timeout=30000,
                        )
                        await page.wait_for_timeout(5000)

                        no_new_rounds = 0
                        for _ in range(MAX_SCROLL_ROUNDS):
                            added = await _append_visible_listings(
                                page,
                                target,
                                keyword,
                                seen_external_ids,
                                processed_external_ids,
                                normalized,
                                per_target_limit,
                            )
                            if len(normalized) >= per_target_limit:
                                break

                            if added == 0:
                                no_new_rounds += 1
                            else:
                                no_new_rounds = 0

                            clicked = await _click_more_button(page)
                            previous_height = await page.evaluate("document.body.scrollHeight")
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            await page.wait_for_timeout(SCROLL_SETTLE_MS)
                            current_height = await page.evaluate("document.body.scrollHeight")

                            if not clicked and current_height == previous_height and no_new_rounds >= 3:
                                break

                        await asyncio.sleep(0.8)
                    except Exception as e:
                        logger.warning("joongna 키워드 '%s' 크롤링 실패: %s", keyword, e)

                    if len(normalized) < per_target_limit:
                        await _append_html_search_pages(
                            keyword,
                            target,
                            seen_external_ids,
                            processed_html_external_ids,
                            normalized,
                            per_target_limit,
                        )

                detail_regions = await _fetch_detail_regions(normalized)

                for title, price, url, external_id, search_keyword in normalized:
                    try:
                        region_name, dong_code = detail_regions.get(external_id, ("", None))
                        results.append(CrawledItem(
                            title=title,
                            price=price,
                            url=url,
                            external_id=f"joongna_{external_id}",
                            source="joongna",
                            region_name=region_name,
                            dong_code=dong_code,
                            target_category=target.category,
                            target_model=target.model,
                            search_keyword=search_keyword,
                        ))
                    except Exception as e:
                        logger.debug("joongna 아이템 파싱 오류: %s", e)

                await asyncio.sleep(2.0)

            await browser.close()

        logger.info("[joongna] %d개 수집", len(results))
        return results


async def _append_visible_listings(
    page,
    target,
    keyword: str,
    seen_external_ids: set[str],
    processed_external_ids: set[str],
    normalized: list[tuple[str, int, str, str, str]],
    limit: int,
) -> int:
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

    added = 0
    for listing in listings:
        try:
            href = listing.get("href")
            text = listing.get("text", "")
            if not href or not text:
                continue

            external_id = href.rstrip("/").split("/")[-1]
            if external_id in processed_external_ids or external_id in seen_external_ids:
                continue
            processed_external_ids.add(external_id)

            title, price = _parse_listing_text(text)
            if price <= 0:
                continue
            if not matches_target_listing(title, price, target):
                continue

            seen_external_ids.add(external_id)
            normalized.append((title, price, href, external_id, keyword))
            added += 1
            if len(normalized) >= limit:
                break
        except Exception as e:
            logger.debug("joongna 아이템 파싱 오류: %s", e)

    return added


async def _append_html_search_pages(
    keyword: str,
    target,
    seen_external_ids: set[str],
    processed_external_ids: set[str],
    normalized: list[tuple[str, int, str, str, str]],
    limit: int,
) -> int:
    added = 0
    no_new_pages = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    async with httpx.AsyncClient(headers=headers, timeout=20) as client:
        for page_num in range(1, MAX_HTML_PAGES + 1):
            if len(normalized) >= limit:
                break
            try:
                response = await client.get(
                    f"https://web.joongna.com/search/{quote(keyword)}",
                    params={"page": page_num} if page_num > 1 else None,
                )
                response.raise_for_status()
            except Exception as e:
                logger.debug("joongna HTML 검색 페이지 조회 실패 (%s, page=%d): %s", keyword, page_num, e)
                break

            page_added = _append_html_listings(
                response.text,
                keyword,
                target,
                seen_external_ids,
                processed_external_ids,
                normalized,
                limit,
            )
            added += page_added

            if page_added == 0:
                no_new_pages += 1
            else:
                no_new_pages = 0
            if no_new_pages >= 2:
                break

            await asyncio.sleep(0.25)

    return added


def _append_html_listings(
    html: str,
    keyword: str,
    target,
    seen_external_ids: set[str],
    processed_external_ids: set[str],
    normalized: list[tuple[str, int, str, str, str]],
    limit: int,
) -> int:
    added = 0
    for external_id, block in _iter_html_product_cards(html):
        if external_id in processed_external_ids or external_id in seen_external_ids:
            continue
        processed_external_ids.add(external_id)

        title, price = _parse_html_product_card(block)
        if price <= 0:
            continue
        if not matches_target_listing(title, price, target):
            continue

        seen_external_ids.add(external_id)
        normalized.append((title, price, f"https://web.joongna.com/product/{external_id}", external_id, keyword))
        added += 1
        if len(normalized) >= limit:
            break
    return added


def _iter_html_product_cards(html: str):
    pattern = re.compile(
        r'<a class="w-full" href="/product/(\d+)">(.*?)(?=<div class="z-auto rounded-none static"><a class="w-full" href="/product/|</div></div></div><div class="flex|\Z)',
        re.S,
    )
    yield from pattern.findall(html)


def _parse_html_product_card(block: str) -> tuple[str, int]:
    alt_match = re.search(r'alt="([^"]+?)\s*이미지"', block)
    title = _html_unescape(alt_match.group(1)).strip() if alt_match else ""

    text = re.sub(r"<[^>]+>", " ", block)
    text = re.sub(r"\s+", " ", _html_unescape(text)).strip()
    price_match = re.search(r"(\d[\d,]*)\s*원", text)
    price = _parse_price(price_match.group(1)) if price_match else 0

    if not title and price_match:
        title = re.sub(r"^인증셀러\s*", "", text[:price_match.start()].strip())
    return title, price


def _html_unescape(value: str) -> str:
    return unescape(value)


async def _click_more_button(page) -> bool:
    for selector in (
        "button:has-text('더보기')",
        "button:has-text('더 불러오기')",
        "a:has-text('더보기')",
        "a:has-text('더 불러오기')",
    ):
        try:
            button = page.locator(selector).first
            if await button.count() == 0:
                continue
            if not await button.is_visible():
                continue
            await button.click(timeout=1500)
            await page.wait_for_timeout(SCROLL_SETTLE_MS)
            return True
        except Exception:
            continue
    return False


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


async def _fetch_detail_regions(items: list[tuple[str, int, str, str, str]]) -> dict[str, tuple[str, str | None]]:
    semaphore = asyncio.Semaphore(8)

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, timeout=20) as client:
        triples = await asyncio.gather(
            *[_fetch_detail_region(client, semaphore, external_id) for _, _, _, external_id, _ in items]
        )
    return {external_id: (region, dong_code) for external_id, region, dong_code in triples}


async def _fetch_detail_region(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    external_id: str,
) -> tuple[str, str, str | None]:
    async with semaphore:
        try:
            response = await client.get(f"https://web.joongna.com/product/{external_id}")
            response.raise_for_status()
            region, dong_code = _extract_region_from_detail_html(response.text)
            return external_id, region, dong_code
        except Exception as e:
            logger.debug("joongna 상세 위치 조회 실패 (%s): %s", external_id, e)
            return external_id, "", None


def _extract_region_from_detail_html(html: str) -> tuple[str, str | None]:
    location_match = re.search(r'\\"locationName\\":\\"([^\\"]+)', html)
    code_match = re.search(r'\\"dongCode\\":\\"([^\\"]+)', html)
    if location_match:
        dong_code = code_match.group(1) if code_match else None
        return region_text_from_dong_code(location_match.group(1), dong_code), dong_code

    address_match = re.search(
        r"(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)\s+"
        r"[^\s]{1,12}(?:시|군|구)\s+[^\s]{1,12}(?:동|읍|면|가)",
        html,
    )
    return (address_match.group(0), None) if address_match else ("", None)
