"""기존 맥북 매물의 SKU를 새 검증 매트릭스로 재배정하고 유령 SKU를 정리한다.

config_matrix가 도입되기 전 만들어진, 칩이 지원하지 않는 조합(M5 Pro 16GB 등)의
SKU를 걷어낸다. 크롤러는 매일 재배정하므로 시간이 지나면 자연 정리되지만,
이 스크립트로 즉시 반영한다.

동작:
1. 맥북 카테고리의 모든 매물에 대해 sku_id를 비우고 재배정(assign) — 유효 조합만 SKU 획득
2. 매물이 하나도 남지 않은 맥북 SKU 삭제 (price_stats는 FK CASCADE로 함께 삭제)

실행: cd backend && .venv/bin/python -m scripts.revalidate_macbook_skus
"""

import asyncio

from sqlalchemy import delete, func, select

from app.db.models.category import Category
from app.db.models.item import Item
from app.db.models.sku import SKU
from app.db.session import AsyncSessionLocal
from app.services.sku_assigner import SkuAssigner


async def main() -> None:
    async with AsyncSessionLocal() as db:
        macbook_id = (
            await db.execute(select(Category.category_id).where(Category.name == "MacBook"))
        ).scalar_one()

        assigner = SkuAssigner()
        await assigner.load(db)

        items = (
            await db.execute(select(Item).where(Item.category_id == macbook_id))
        ).scalars().all()

        reassigned = 0
        cleared = 0
        for item in items:
            before = item.sku_id
            item.sku_id = None  # 무효 조합이면 NULL로 남아 잘못된 SKU에서 빠진다
            await assigner.assign(db, item)
            if item.sku_id is not None:
                reassigned += 1
            elif before is not None:
                cleared += 1
        await db.commit()

        # 매물이 하나도 참조하지 않는 맥북 SKU 삭제
        orphan_ids = (
            await db.execute(
                select(SKU.sku_id)
                .outerjoin(Item, Item.sku_id == SKU.sku_id)
                .where(SKU.category_id == macbook_id)
                .group_by(SKU.sku_id)
                .having(func.count(Item.item_id) == 0)
            )
        ).scalars().all()

        if orphan_ids:
            await db.execute(delete(SKU).where(SKU.sku_id.in_(orphan_ids)))
            await db.commit()

        remaining = (
            await db.execute(
                select(func.count(SKU.sku_id)).where(SKU.category_id == macbook_id)
            )
        ).scalar_one()

        print(f"매물 {len(items)}개 처리 — SKU 재배정 {reassigned}, 무효로 SKU 해제 {cleared}")
        print(f"유령 SKU 삭제 {len(orphan_ids)}개, 남은 맥북 SKU {remaining}개")


if __name__ == "__main__":
    asyncio.run(main())
