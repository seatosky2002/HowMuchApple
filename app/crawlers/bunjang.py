import asyncio
import logging

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

                    normalized = []
                    for item in data.get("list", []):
                        try:
                            pid = str(item.get("pid", ""))
                            title = item.get("name", "").strip()
                            price = int(item.get("price", 0))
                            if price <= 0 or not pid:
                                continue

                            url = f"https://m.bunjang.co.kr/products/{pid}"
                            region = (item.get("location") or "").strip()
                            normalized.append((title, price, url, pid, region))
                        except Exception as e:
                            logger.debug("bunjang 아이템 파싱 오류: %s", e)

                    detail_regions = await _fetch_detail_regions(client, normalized)

                    for title, price, url, pid, region in normalized:
                        try:
                            results.append(CrawledItem(
                                title=title,
                                price=price,
                                url=url,
                                external_id=f"bunjang_{pid}",
                                source="bunjang",
                                region_name=region or detail_regions.get(pid, ""),
                            ))
                        except Exception as e:
                            logger.debug("bunjang 아이템 파싱 오류: %s", e)

                    await asyncio.sleep(1.0)
                except Exception as e:
                    logger.warning("bunjang 키워드 '%s' 크롤링 실패: %s", keyword, e)

        logger.info("[bunjang] %d개 수집", len(results))
        return results


async def _fetch_detail_regions(
    client: httpx.AsyncClient,
    items: list[tuple[str, int, str, str, str]],
) -> dict[str, str]:
    missing_region_pids = [pid for _, _, _, pid, region in items if not region]
    if not missing_region_pids:
        return {}

    semaphore = asyncio.Semaphore(8)
    pairs = await asyncio.gather(
        *[_fetch_detail_region(client, semaphore, pid) for pid in missing_region_pids]
    )
    return {pid: region for pid, region in pairs if region}


async def _fetch_detail_region(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    pid: str,
) -> tuple[str, str]:
    async with semaphore:
        try:
            response = await client.get(f"https://api.bunjang.co.kr/api/pms/v1/products/{pid}/detail/web")
            response.raise_for_status()
            return pid, _extract_region_from_detail(response.json())
        except Exception as e:
            logger.debug("bunjang 상세 위치 조회 실패 (%s): %s", pid, e)
            return pid, ""


def _extract_region_from_detail(data: dict) -> str:
    product = data.get("data", {}).get("product", {})
    geo = product.get("geo") or {}
    address = (geo.get("address") or "").strip()
    if address:
        return address

    for group in product.get("trades") or []:
        if group.get("title") != "직거래 희망 장소":
            continue
        for content in group.get("contents") or []:
            content = str(content).strip()
            if content:
                return content

    return ""
