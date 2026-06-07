import asyncio
import logging
import re

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
                        f"https://www.daangn.com/search/{keyword}?in=서울특별시&category_id=607",
                        wait_until="networkidle",
                        timeout=30000,
                    )
                    await page.wait_for_selector("article[data-testid]", timeout=10000)

                    articles = await page.query_selector_all("article[data-testid]")
                    for article in articles[:30]:
                        try:
                            title_el = await article.query_selector("strong.title")
                            price_el = await article.query_selector("p.price")
                            region_el = await article.query_selector("p.region")
                            link_el = await article.query_selector("a")

                            if not (title_el and price_el and link_el):
                                continue

                            title = (await title_el.inner_text()).strip()
                            price_text = (await price_el.inner_text()).strip()
                            price = _parse_price(price_text)
                            if price <= 0:
                                continue

                            href = await link_el.get_attribute("href")
                            if not href:
                                continue
                            url = f"https://www.daangn.com{href}" if href.startswith("/") else href
                            external_id = href.rstrip("/").split("/")[-1]

                            region = ""
                            if region_el:
                                region_text = (await region_el.inner_text()).strip()
                                region = f"서울특별시 {region_text}"

                            results.append(CrawledItem(
                                title=title,
                                price=price,
                                url=url,
                                external_id=f"daangn_{external_id}",
                                source="daangn",
                                region_name=region,
                            ))
                        except Exception as e:
                            logger.debug("daangn 아이템 파싱 오류: %s", e)

                    await asyncio.sleep(1.5)
                except Exception as e:
                    logger.warning("daangn 키워드 '%s' 크롤링 실패: %s", keyword, e)

            await browser.close()

        logger.info("[daangn] %d개 수집", len(results))
        return results


def _parse_price(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return 0
    price = int(digits)
    if price < 1000:
        price *= 10000
    return price
