import asyncio
import logging
import re

from playwright.async_api import async_playwright

from app.crawlers.base import BaseCrawler, CrawledItem

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
                        f"https://web.joongna.com/search/{keyword}",
                        wait_until="networkidle",
                        timeout=30000,
                    )
                    await page.wait_for_selector("ul.search-result-list li", timeout=10000)

                    items_el = await page.query_selector_all("ul.search-result-list li a")
                    for item_el in items_el[:30]:
                        try:
                            title_el = await item_el.query_selector(".title")
                            price_el = await item_el.query_selector(".price")
                            location_el = await item_el.query_selector(".location")

                            if not (title_el and price_el):
                                continue

                            title = (await title_el.inner_text()).strip()
                            price_text = (await price_el.inner_text()).strip()
                            price = _parse_price(price_text)
                            if price <= 0:
                                continue

                            href = await item_el.get_attribute("href")
                            if not href:
                                continue
                            url = f"https://web.joongna.com{href}" if href.startswith("/") else href
                            external_id = href.rstrip("/").split("/")[-1]

                            region = ""
                            if location_el:
                                loc_text = (await location_el.inner_text()).strip()
                                region = f"서울특별시 {loc_text}"

                            results.append(CrawledItem(
                                title=title,
                                price=price,
                                url=url,
                                external_id=f"joongna_{external_id}",
                                source="joongna",
                                region_name=region,
                            ))
                        except Exception as e:
                            logger.debug("joongna 아이템 파싱 오류: %s", e)

                    await asyncio.sleep(2.0)
                except Exception as e:
                    logger.warning("joongna 키워드 '%s' 크롤링 실패: %s", keyword, e)

            await browser.close()

        logger.info("[joongna] %d개 수집", len(results))
        return results


def _parse_price(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return 0
    price = int(digits)
    if price < 1000:
        price *= 10000
    return price
