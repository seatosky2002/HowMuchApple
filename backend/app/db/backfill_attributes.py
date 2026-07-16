"""기존 item 전체에 속성 추출 + SKU 배정을 소급 적용한다. (plan.md Phase 3)

실행: python -m app.db.backfill_attributes
idempotent — 재실행 시 같은 결과로 수렴한다.
"""

import asyncio
import collections

from sqlalchemy import select

from app.db.models.item import Item
from app.db.session import AsyncSessionLocal, engine
from app.services.sku_assigner import SkuAssigner

BATCH_SIZE = 500


async def backfill() -> None:
    stats: collections.Counter = collections.Counter()
    per_category: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)

    async with AsyncSessionLocal() as db:
        assigner = SkuAssigner()
        await assigner.load(db)

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
                stats["total"] += 1
                extraction = await assigner.assign(db, item)
                if extraction is None:
                    stats["no_target"] += 1
                    continue
                counter = per_category[extraction.category]
                counter["total"] += 1
                if not extraction.title_matches_target:
                    counter["noise"] += 1
                elif extraction.sku_ready:
                    counter["sku_assigned"] += 1
                if extraction.is_sold:
                    stats["sold"] += 1
            await db.commit()
            print(f"  ... {stats['total']}건 처리 (last_id={last_id})")

    await engine.dispose()

    print("\n=== 백필 완료 ===")
    print(f"전체 {stats['total']}건 / 타깃 미해결 {stats['no_target']}건 / sold 마킹 {stats['sold']}건")
    for category, counter in sorted(per_category.items()):
        assigned, total = counter["sku_assigned"], counter["total"]
        rate = 100 * assigned / total if total else 0
        print(f"  {category}: SKU 배정 {assigned}/{total} ({rate:.1f}%), 노이즈 {counter['noise']}")


if __name__ == "__main__":
    asyncio.run(backfill())
