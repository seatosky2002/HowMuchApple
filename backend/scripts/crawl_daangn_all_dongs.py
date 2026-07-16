"""수집한 서울·경기 전 동 코드로 당근 크롤링 실행 (수동 실행/DB 미사용).

docs/daangn_seoul_gyeonggi_region_codes.md 에서 동 코드를 읽어, 각 동 × 타겟 모델을
`?in=<동코드>&search=<모델명>` 으로 검색해 매물을 수집한다. external_id로 전역 중복
제거 후 CSV로 저장하고 요약을 출력한다.
"""
import asyncio
import csv
import re
import sys
from collections import Counter
from urllib.parse import quote

import httpx

sys.path.insert(0, "/Users/byunmingyu/Desktop/HowMuchApple/HowMuchApple/backend")
from app.crawlers.daangn import _extract_cards, _parse_listing_text, _extract_external_id
from app.crawlers.filters import matches_target_listing
from app.crawlers.targets import CRAWL_TARGETS

MD_PATH = "/Users/byunmingyu/Desktop/HowMuchApple/HowMuchApple/docs/daangn_seoul_gyeonggi_region_codes.md"
OUT_CSV = "/Users/byunmingyu/Desktop/HowMuchApple/HowMuchApple/backend/exports/daangn_all_dongs_crawl.csv"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
CONCURRENCY = 5
DELAY_S = 0.35
BACKOFF_S = 15
MAX_RETRY = 2

CODE_IN_MD_RE = re.compile(r"\|\s*[^|]+\|\s*`([^`]+)`\s*\|")


def load_codes() -> list[str]:
    codes = []
    with open(MD_PATH, encoding="utf-8") as fp:
        for line in fp:
            m = CODE_IN_MD_RE.search(line)
            if m:
                codes.append(m.group(1))
    return list(dict.fromkeys(codes))


async def fetch(client, sem, region, keyword):
    url = f"https://www.daangn.com/kr/buy-sell/?in={quote(region)}&search={quote(keyword)}"
    async with sem:
        for attempt in range(MAX_RETRY + 1):
            try:
                r = await client.get(url)
                if r.status_code == 429:
                    await asyncio.sleep(BACKOFF_S)
                    continue
                r.raise_for_status()
                await asyncio.sleep(DELAY_S)
                return r.text
            except Exception:
                if attempt == MAX_RETRY:
                    return None
                await asyncio.sleep(2)
        return None


async def main():
    codes = load_codes()
    targets = CRAWL_TARGETS
    print(f"동 코드 {len(codes)}개 × 타겟 {len(targets)}개 = {len(codes)*len(targets)} 검색 예정", flush=True)

    seen: set[str] = set()
    rows = []
    per_target = Counter()
    per_region = Counter()
    sem = asyncio.Semaphore(CONCURRENCY)
    done = 0
    total = len(codes) * len(targets)

    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=20, follow_redirects=True) as client:
        # (region, target) 조합을 배치로 처리
        combos = [(region, target) for target in targets for region in codes]
        for i in range(0, len(combos), CONCURRENCY):
            batch = combos[i:i + CONCURRENCY]
            htmls = await asyncio.gather(*[fetch(client, sem, r, t.primary_keyword) for r, t in batch])
            for (region, target), html in zip(batch, htmls):
                done += 1
                if not html:
                    continue
                anchor_dong = region.rsplit("-", 1)[0]
                for href, text in _extract_cards(html):
                    title, price, item_region = _parse_listing_text(text)
                    if price <= 0 or not matches_target_listing(title, price, target):
                        continue
                    ext = _extract_external_id(href)
                    if ext in seen:
                        continue
                    seen.add(ext)
                    full_url = href if href.startswith("http") else f"https://www.daangn.com{href}"
                    rows.append({
                        "external_id": ext,
                        "category": target.category,
                        "model": target.model,
                        "title": title,
                        "price": price,
                        "region": item_region or anchor_dong,
                        "search_region_code": region,
                        "url": full_url,
                    })
                    per_target[target.model] += 1
                    per_region[item_region or anchor_dong] += 1
            if (i // CONCURRENCY) % 20 == 0:
                print(f"[진행] {done}/{total} 검색 완료, 누적 매물 {len(rows)}개", flush=True)

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()) if rows else
                           ["external_id", "category", "model", "title", "price", "region", "search_region_code", "url"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n=== 완료 ===")
    print(f"총 고유 매물: {len(rows)}개 → {OUT_CSV}")
    print(f"\n모델 top 15:")
    for model, n in per_target.most_common(15):
        print(f"  {n:5d}  {model}")
    print(f"\n지역(동) top 15:")
    for region, n in per_region.most_common(15):
        print(f"  {n:5d}  {region}")


asyncio.run(main())
