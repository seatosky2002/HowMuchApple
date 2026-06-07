import asyncio
import logging
import re

import httpx

from app.crawlers.base import BaseCrawler, CrawledItem

logger = logging.getLogger(__name__)

KEYWORDS = ["아이폰", "아이패드", "맥북", "애플워치", "에어팟"]
BUNJANG_API = "https://api.bunjang.co.kr/api/1/find_v2.json"


class BunjangCrawler(BaseCrawler):
    platform = "bunjang"

    async def crawl(self) -> list[CrawledItem]:
        results: list[CrawledItem] = []

        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://m.bunjang.co.kr/"},
            timeout=20,
        ) as client:
            for keyword in KEYWORDS:
                try:
                    resp = await client.get(
                        BUNJANG_API,
                        params={
                            "q": keyword,
                            "order": "date",
                            "page": 0,
                            "n": 30,
                            "lon": "126.9780",
                            "lat": "37.5665",
                            "distance": 0,
                        },
                    )
                    data = resp.json()

                    for item in data.get("list", []):
                        try:
                            pid = str(item.get("pid", ""))
                            title = item.get("name", "").strip()
                            price = int(item.get("price", 0))
                            if price <= 0 or not pid:
                                continue

                            url = f"https://m.bunjang.co.kr/products/{pid}"
                            location = item.get("location", "")
                            region = f"서울특별시 {location}" if location else ""

                            results.append(CrawledItem(
                                title=title,
                                price=price,
                                url=url,
                                external_id=f"bunjang_{pid}",
                                source="bunjang",
                                region_name=region,
                            ))
                        except Exception as e:
                            logger.debug("bunjang 아이템 파싱 오류: %s", e)

                    await asyncio.sleep(1.0)
                except Exception as e:
                    logger.warning("bunjang 키워드 '%s' 크롤링 실패: %s", keyword, e)

        logger.info("[bunjang] %d개 수집", len(results))
        return results
