import asyncio
import hashlib
from html import unescape
import logging
import re
from urllib.parse import quote, urlparse

import httpx
from playwright.async_api import async_playwright

from app.crawlers.base import BaseCrawler, CrawledItem, strip_status_badge
from app.crawlers.filters import matches_target_title

logger = logging.getLogger(__name__)
MAX_SCROLL_ROUNDS = 25
SCROLL_SETTLE_MS = 1200


class DaangnCrawler(BaseCrawler):
    platform = "daangn"

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

                for keyword in target.keywords:
                    if len(normalized) >= per_target_limit:
                        break
                    try:
                        await page.goto(
                            f"https://www.daangn.com/kr/buy-sell/?search={quote(keyword)}",
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
                        logger.warning("daangn 키워드 '%s' 크롤링 실패: %s", keyword, e)

                detail_regions = await _fetch_detail_regions(normalized)

                for title, price, href, external_id, region, search_keyword, status in normalized:
                    try:
                        results.append(CrawledItem(
                            title=title,
                            price=price,
                            url=href,
                            external_id=f"daangn_{external_id}",
                            source="daangn",
                            region_name=detail_regions.get(external_id) or region,
                            target_category=target.category,
                            target_model=target.model,
                            search_keyword=search_keyword,
                            status=status,
                        ))
                    except Exception as e:
                        logger.debug("daangn 아이템 파싱 오류: %s", e)

                await asyncio.sleep(1.5)

            await browser.close()

        logger.info("[daangn] %d개 수집", len(results))
        return results


async def _append_visible_listings(
    page,
    target,
    keyword: str,
    seen_external_ids: set[str],
    processed_external_ids: set[str],
    normalized: list[tuple[str, int, str, str, str, str]],
    limit: int,
) -> int:
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

    added = 0
    for listing in listings:
        try:
            href = listing.get("href")
            text = listing.get("text", "")
            if not href or not text:
                continue

            external_id = _extract_external_id(href)
            if external_id in processed_external_ids or external_id in seen_external_ids:
                continue
            processed_external_ids.add(external_id)

            title, price, region, status = _parse_listing_text(text)
            if price <= 0:
                continue
            if not matches_target_title(title, target):
                continue

            seen_external_ids.add(external_id)
            normalized.append((title, price, href, external_id, region, keyword, status))
            added += 1
            if len(normalized) >= limit:
                break
        except Exception as e:
            logger.debug("daangn 아이템 파싱 오류: %s", e)

    return added


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


def _parse_listing_text(text: str) -> tuple[str, int, str, str]:
    # "거래완료"/"예약중" 등 상태 배지가 제목 앞에 붙어서 오므로 먼저 분리
    text, status = strip_status_badge(text)

    match = re.search(r"(나눔|\d[\d,]*원)", text)
    if not match:
        return text.strip(), 0, "", status

    title = text[:match.start()].strip()
    price = _parse_price(match.group(1))
    after_price = text[match.end():].strip()
    region = after_price.split("·", 1)[0].strip() if after_price else ""
    return title, price, region, status


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


async def _fetch_detail_regions(items: list[tuple[str, int, str, str, str, str, str]]) -> dict[str, str]:
    semaphore = asyncio.Semaphore(8)

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, timeout=20) as client:
        pairs = await asyncio.gather(
            *[_fetch_detail_region(client, semaphore, url, external_id) for _, _, url, external_id, _, _, _ in items]
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
