"""기존 item 전체의 지역 연결(emd_id)을 소급 적용한다.

seed_regions로 행정구역 마스터를 채운 뒤 실행한다. region_text를 다시 매칭해
emd_id를 채우고, 매칭된 경우 비어 있는 region_sgg/region_emd 텍스트도
마스터 기준으로 보강한다.

- daangn: 주소가 동 이름뿐이므로 후보를 서울·경기로 제한, 유일할 때만 매칭
- bunjang/joongna: 전체 주소 텍스트로 일반 매칭

idempotent — 재실행 시 같은 결과로 수렴한다.
실행: python -m app.db.backfill_regions
"""

import asyncio
import collections

from sqlalchemy import select

from app.db.models.item import Item
from app.db.models.region import EMD, SD, SGG
from app.db.session import AsyncSessionLocal, engine
from app.services.region_matcher import resolve_emd_id

BATCH_SIZE = 500
DAANGN_SD_SCOPE = ("서울특별시", "경기도")


async def backfill() -> None:
    stats: collections.Counter = collections.Counter()
    per_source: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    # 같은 region_text는 결과가 같으므로 캐시해서 매칭 쿼리를 줄인다 (소스별 분리 —
    # daangn은 시도 제한 규칙이 다르다)
    cache: dict[tuple[str, str], int | None] = {}

    async with AsyncSessionLocal() as db:
        emd_names: dict[int, tuple[str, str]] = {}  # emd_id -> (sgg_name, emd_name)
        rows = (
            await db.execute(
                select(EMD.emd_id, SGG.name, EMD.name).join(SGG, EMD.sgg_id == SGG.sgg_id)
            )
        ).all()
        for emd_id, sgg_name, emd_name in rows:
            emd_names[emd_id] = (sgg_name, emd_name)

        last_id = 0
        while True:
            items = (
                (
                    await db.execute(
                        select(Item).where(Item.item_id > last_id).order_by(Item.item_id).limit(BATCH_SIZE)
                    )
                )
                .scalars()
                .all()
            )
            if not items:
                break
            for item in items:
                last_id = item.item_id
                counter = per_source[item.source]
                counter["total"] += 1
                if not item.region_text:
                    counter["no_text"] += 1
                    continue

                cache_key = (item.source, item.region_text)
                if cache_key in cache:
                    emd_id = cache[cache_key]
                else:
                    if item.source == "daangn":
                        emd_id = await resolve_emd_id(
                            db, item.region_text, preferred_sd_name="", allowed_sd_names=DAANGN_SD_SCOPE
                        )
                    else:
                        emd_id = await resolve_emd_id(db, item.region_text)
                    cache[cache_key] = emd_id

                if emd_id is None:
                    counter["unmatched"] += 1
                    continue

                counter["matched"] += 1
                if item.emd_id != emd_id:
                    item.emd_id = emd_id
                    counter["updated"] += 1
                sgg_name, emd_name = emd_names[emd_id]
                if not item.region_sgg:
                    item.region_sgg = sgg_name
                if not item.region_emd:
                    item.region_emd = emd_name
            await db.commit()
            stats["total"] += len(items)
            print(f"  ... {stats['total']}건 처리 (last_id={last_id})")

    await engine.dispose()

    print("\n=== 지역 백필 완료 ===")
    for source, counter in sorted(per_source.items()):
        matched, total = counter["matched"], counter["total"]
        rate = 100 * matched / total if total else 0
        print(
            f"  {source}: 매칭 {matched}/{total} ({rate:.1f}%) — 신규 연결 {counter['updated']},"
            f" 주소없음 {counter['no_text']}, 미매칭 {counter['unmatched']}"
        )


if __name__ == "__main__":
    asyncio.run(backfill())
