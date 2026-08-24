"""같은 읍면동이 "구 없는 시"와 "시 구" 아래 중복 적재된 것을 하나로 합친다.

배경: 행정구역 시드가 두 시점에 걸쳐 들어가면서, 구가 설치된 시(부천·화성·수원·성남
등 13곳)의 읍면동이 `부천시 중동`과 `부천시 원미구 중동`으로 **둘 다** 존재한다.
그래서 매물 주소가 풀네임("경기도 부천시 원미구 중동")이어도 후보가 2개가 되어
region_matcher가 "지역 매칭 모호"로 매칭을 포기한다. 동 이름만 오는 당근 주소는 더 심하다.

정리 방식:
1. (시도, 시 이름, 읍면동 이름)이 같은 emd 행들을 한 그룹으로 본다
2. 그룹에서 **매물이 가장 많은 행을 정본**으로 남긴다 (같으면 구 없는 쪽 → 낮은 id 순).
   매물·시세 이력이 붙어 있는 쪽을 살려서 price_stats 손실을 만들지 않는다.
3. 나머지 행의 item/watchlist/price_stats 참조를 정본으로 옮기고 그 행을 삭제
4. 자식이 없어진 sgg 행도 삭제

멱등하다 — 두 번 돌려도 두 번째는 0건이 나온다.
실행: cd backend && .venv/bin/python -m app.db.dedupe_regions [--dry-run]
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict

from sqlalchemy import delete, func, select, update

from app.db.models.alert import Watchlist
from app.db.models.item import Item
from app.db.models.region import EMD, SD, SGG
from app.db.models.sku import PriceStats
from app.db.session import AsyncSessionLocal


def _city_of(sgg_name: str) -> str:
    """"부천시 원미구" → "부천시" (구가 없으면 그대로)."""
    return sgg_name.split(" ", 1)[0]


async def main(dry_run: bool = False) -> None:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(EMD.emd_id, EMD.name, SGG.sgg_id, SGG.name, SD.name)
                .join(SGG, SGG.sgg_id == EMD.sgg_id)
                .join(SD, SD.sd_id == SGG.sd_id)
            )
        ).all()
        item_counts = dict(
            (
                await db.execute(
                    select(Item.emd_id, func.count()).where(Item.emd_id.is_not(None)).group_by(Item.emd_id)
                )
            ).all()
        )

        groups: dict[tuple[str, str, str], list[tuple[int, int, str]]] = defaultdict(list)
        for emd_id, emd_name, sgg_id, sgg_name, sd_name in rows:
            groups[(sd_name, _city_of(sgg_name), emd_name)].append((emd_id, sgg_id, sgg_name))

        merged = moved_items = moved_stats = dropped_stats = 0
        for (sd_name, city, emd_name), members in sorted(groups.items()):
            if len(members) < 2:
                continue
            # 구 없는 "시" 행이 섞여 있을 때만 병합한다. 한 시의 서로 다른 두 구에
            # 같은 이름의 동이 실제로 존재할 수 있어(별개 지역), 시드 중복으로
            # 확실히 판별되는 경우만 건드린다.
            if all(" " in sgg_name for _, _, sgg_name in members):
                continue
            # 매물 많은 쪽 → 구 없는 쪽 → 낮은 id 순으로 정본 선정
            members.sort(key=lambda m: (-item_counts.get(m[0], 0), " " in m[2], m[0]))
            keep_id = members[0][0]
            drop_ids = [m[0] for m in members[1:]]
            keep_label = f"{sd_name} {members[0][2]} {emd_name}"
            drop_label = ", ".join(f"{m[2]} {emd_name}({item_counts.get(m[0], 0)}건)" for m in members[1:])
            print(f"  {keep_label}({item_counts.get(keep_id, 0)}건) ← {drop_label}")
            merged += len(drop_ids)
            if dry_run:
                continue

            # price_stats는 (sku_id, emd_id, bucket_ts)가 PK라 정본에 같은 키가 이미
            # 있으면 옮길 수 없다 — 그 행만 버리고 나머지는 옮긴다.
            kept_keys = set(
                (
                    await db.execute(
                        select(PriceStats.sku_id, PriceStats.bucket_ts).where(PriceStats.emd_id == keep_id)
                    )
                ).all()
            )
            for drop_id in drop_ids:
                stat_rows = (
                    await db.execute(
                        select(PriceStats.sku_id, PriceStats.bucket_ts).where(PriceStats.emd_id == drop_id)
                    )
                ).all()
                for sku_id, bucket_ts in stat_rows:
                    if (sku_id, bucket_ts) in kept_keys:
                        await db.execute(
                            delete(PriceStats).where(
                                PriceStats.emd_id == drop_id,
                                PriceStats.sku_id == sku_id,
                                PriceStats.bucket_ts == bucket_ts,
                            )
                        )
                        dropped_stats += 1
                    else:
                        await db.execute(
                            update(PriceStats)
                            .where(
                                PriceStats.emd_id == drop_id,
                                PriceStats.sku_id == sku_id,
                                PriceStats.bucket_ts == bucket_ts,
                            )
                            .values(emd_id=keep_id)
                        )
                        kept_keys.add((sku_id, bucket_ts))
                        moved_stats += 1

            result = await db.execute(
                update(Item).where(Item.emd_id.in_(drop_ids)).values(emd_id=keep_id)
            )
            moved_items += result.rowcount or 0
            await db.execute(update(Watchlist).where(Watchlist.emd_id.in_(drop_ids)).values(emd_id=keep_id))
            await db.execute(delete(EMD).where(EMD.emd_id.in_(drop_ids)))

        if not dry_run:
            await db.commit()

        empty_sggs = (
            await db.execute(
                select(SGG.sgg_id, SGG.name)
                .outerjoin(EMD, EMD.sgg_id == SGG.sgg_id)
                .group_by(SGG.sgg_id, SGG.name)
                .having(func.count(EMD.emd_id) == 0)
            )
        ).all()
        if empty_sggs and not dry_run:
            await db.execute(delete(SGG).where(SGG.sgg_id.in_([s[0] for s in empty_sggs])))
            await db.commit()

        print(
            f"\n중복 emd {merged}개 병합 / 매물 {moved_items}건 재연결 / "
            f"price_stats {moved_stats}행 이동·{dropped_stats}행 정리 / "
            f"빈 sgg {len(empty_sggs)}개 삭제" + (" (dry-run — 반영 안 함)" if dry_run else "")
        )


if __name__ == "__main__":
    asyncio.run(main(dry_run="--dry-run" in sys.argv))
