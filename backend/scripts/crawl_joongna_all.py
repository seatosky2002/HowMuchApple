"""중고나라 전량 수집 크롤 (수동 실행/DB 미사용).

중고나라 웹 검색 API(search-api.joongna.com/v3/search/all)를 모델 키워드별로
전 페이지 순회해 매물을 수집한다. 각 매물의 locationNames로 지역을 라벨링하고,
seq 기준 전역 중복 제거 후 CSV로 저장, 서울/경기/기타/무지역 통계를 출력한다.

참고: locationFilter 파라미터는 앱 전용이라 웹 API에선 500 → 사용 불가.
대신 전국 검색 페이지네이션이 동별 키워드 검색("천호동 아이폰")의 상위집합임을
검증했으므로 이 방식을 쓴다.
"""
import asyncio
import csv
import sys
from collections import Counter

import httpx

sys.path.insert(0, "/Users/byunmingyu/Desktop/HowMuchApple/HowMuchApple/backend")
from app.crawlers.filters import matches_target_listing
from app.crawlers.targets import CRAWL_TARGETS

OUT_CSV = "/Users/byunmingyu/Desktop/HowMuchApple/HowMuchApple/backend/exports/joongna_all_regions_crawl.csv"
API = "https://search-api.joongna.com/v3/search/all"

CONCURRENCY = 4          # 동시에 진행하는 키워드 수
PAGE_DELAY_S = 0.3
MAX_PAGES = 40
MAX_RETRY = 3
BACKOFF_S = 10

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Content-Type": "application/json",
    "Origin": "https://web.joongna.com",
    "Referer": "https://web.joongna.com/",
}


def search_body(word: str, page: int) -> dict:
    return {
        "osType": 2, "firstQuantity": 50, "quantity": 50, "jnPayYn": "ALL",
        "categoryFilter": [{"categoryDepth": 0, "categorySeq": 0}],
        "priceFilter": {"minPrice": 0, "maxPrice": 100000000},
        "sort": "RECENT_SORT", "saleYn": "SALE_N", "parcelFeeYn": "ALL",
        "page": page, "searchWord": word,
        "adjustSearchKeyword": True, "keywordSource": "INPUT_KEYWORD", "registPeriod": "ALL",
    }


async def fetch_page(client: httpx.AsyncClient, word: str, page: int) -> list[dict] | None:
    for attempt in range(MAX_RETRY + 1):
        try:
            r = await client.post(API, json=search_body(word, page))
            if r.status_code in (429, 500, 502, 503):
                await asyncio.sleep(BACKOFF_S * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json().get("data", {})
            return [i for i in data.get("items", []) if i.get("objectType") == "product"]
        except Exception:
            if attempt == MAX_RETRY:
                return None
            await asyncio.sleep(3)
    return None


async def crawl_keyword(client, sem, target, keyword, seen: set, rows: list,
                        per_target: Counter, per_sido: Counter):
    async with sem:
        empty_pages = 0
        for page in range(MAX_PAGES):
            items = await fetch_page(client, keyword, page)
            if items is None:
                break
            new_count = 0
            for it in items:
                seq = it.get("seq")
                if not seq or seq in seen:
                    continue
                seen.add(seq)
                new_count += 1
                title = (it.get("title") or "").strip()
                price = it.get("price") or 0
                if price <= 0 or not matches_target_listing(title, price, target):
                    continue
                locs = it.get("locationNames") or []
                region = locs[0] if locs else ""
                sido = region.split()[0] if region else "(무지역)"
                rows.append({
                    "external_id": f"joongna_{seq}",
                    "category": target.category,
                    "model": target.model,
                    "title": title,
                    "price": price,
                    "region": region,
                    "search_keyword": keyword,
                    "url": f"https://web.joongna.com/product/{seq}",
                })
                per_target[target.model] += 1
                per_sido[sido] += 1
            if new_count == 0:
                empty_pages += 1
                if empty_pages >= 2:
                    break
            else:
                empty_pages = 0
            await asyncio.sleep(PAGE_DELAY_S)


async def main():
    combos = [(t, kw) for t in CRAWL_TARGETS for kw in t.keywords]
    print(f"타겟 {len(CRAWL_TARGETS)}개 / 키워드 {len(combos)}개 크롤 시작", flush=True)

    seen: set = set()
    rows: list[dict] = []
    per_target: Counter = Counter()
    per_sido: Counter = Counter()
    sem = asyncio.Semaphore(CONCURRENCY)
    done = 0

    async with httpx.AsyncClient(headers=HEADERS, timeout=25) as client:
        async def run_one(t, kw):
            nonlocal done
            await crawl_keyword(client, sem, t, kw, seen, rows, per_target, per_sido)
            done += 1
            if done % 10 == 0:
                print(f"[진행] 키워드 {done}/{len(combos)} 완료, 누적 매물 {len(rows)}개", flush=True)

        await asyncio.gather(*[run_one(t, kw) for t, kw in combos])

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as fp:
        fields = ["external_id", "category", "model", "title", "price", "region", "search_keyword", "url"]
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print("\n=== 완료 ===", flush=True)
    print(f"총 고유 매물: {len(rows)}개 → {OUT_CSV}")
    print("\n시도별 분포:")
    for sido, n in per_sido.most_common():
        print(f"  {n:6d}  {sido}")
    seoul_gg = sum(n for s, n in per_sido.items() if s.startswith(("서울", "경기")))
    print(f"\n서울/경기 소계: {seoul_gg}개")
    print("\n모델 top 15:")
    for model, n in per_target.most_common(15):
        print(f"  {n:5d}  {model}")


asyncio.run(main())
