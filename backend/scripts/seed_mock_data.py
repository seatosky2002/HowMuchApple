"""로컬 개발용 mock 데이터 시더.

기존 sku/item/price_stats/watchlist/alert를 비우고, 대표 iPhone SKU들에 대해
- 실제 분포를 흉내 낸 활성 매물(정상가 + 내구제류 저가 노이즈 + 미개봉 고가)
- 지난 4주 일별 price_stats 스냅샷
을 생성한다. 시세 페이지(평균/최저/최고, 추이 차트, 플랫폼 비교, 지역별 표)를
전부 로컬에서 확인할 수 있는 최소 데이터셋.

실행:
    cd backend && .venv/bin/python -m scripts.seed_mock_data
"""

import asyncio
import math
import random
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import delete, select

from app.db.models.alert import Alert, Watchlist
from app.db.models.category import Attribute, AttributeOption, Category
from app.db.models.item import Item, ItemAttributeValue, ItemStatus
from app.db.models.region import EMD
from app.db.models.sku import SKU, SKUAttribute, PriceStats
from app.db.session import AsyncSessionLocal

random.seed(42)

DAYS = 28
SOURCES = ("bunjang", "joongna", "daangn")
SOURCE_WEIGHTS = (0.45, 0.45, 0.10)

# (모델 옵션 value, 용량 옵션 value, 기준가, 매물 수)
MOCK_SKUS = [
    ("iPhone 17e", "256GB", 850_000, 120),
    ("iPhone 17e", "128GB", 720_000, 60),
    ("iPhone 17", "256GB", 1_150_000, 90),
    ("iPhone 16", "128GB", 620_000, 70),
]

NORMAL_TITLES = [
    "아이폰 {m} {s} 팝니다",
    "아이폰{m} {s} S급 판매",
    "아이폰 {m} {s} 상태 좋아요",
    "iPhone {m} {s} 급처",
    "아이폰 {m} {s} 배터리 100%",
    "아이폰{m} {s} 풀박스",
]
SEALED_TITLES = [
    "(미개봉) 아이폰 {m} {s} 자급제",
    "아이폰 {m} {s} 미개봉 새상품",
]
JUNK_TITLES = [
    "별달**{n}S2(아이폰{m} {s})",
    "쇼코*라(아이폰{m} {s})",
    "이*읏(아이폰{m} {s})",
]


def _price_round(value: float) -> int:
    return max(int(round(value / 1000) * 1000), 10_000)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        category_id = (
            await db.execute(select(Category.category_id).where(Category.name == "iPhone"))
        ).scalar_one()
        emd_ids = (await db.execute(select(EMD.emd_id))).scalars().all()

        async def option_of(code: str, value: str) -> tuple[int, int]:
            row = (
                await db.execute(
                    select(Attribute.attribute_id, AttributeOption.option_id)
                    .join(AttributeOption, AttributeOption.attribute_id == Attribute.attribute_id)
                    .where(Attribute.code == code, AttributeOption.value == value)
                )
            ).one_or_none()
            if row is None:
                raise SystemExit(f"카탈로그에 {code}={value} 옵션이 없습니다. seed_catalog를 먼저 실행하세요.")
            return row.attribute_id, row.option_id

        # 기존 파생 데이터 초기화 (카탈로그/지역은 유지)
        for model in (Alert, Watchlist, ItemAttributeValue, Item, PriceStats, SKUAttribute, SKU):
            await db.execute(delete(model))
        await db.commit()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        total_items = 0
        total_stats = 0

        for model_value, storage_value, base_price, item_count in MOCK_SKUS:
            fingerprint = f"{category_id}:model={model_value}|storage={storage_value}"
            sku = SKU(category_id=category_id, fingerprint=fingerprint, search_count=random.randint(3, 40))
            db.add(sku)
            await db.flush()
            for code, value in (("model", model_value), ("storage", storage_value)):
                attr_id, opt_id = await option_of(code, value)
                db.add(SKUAttribute(sku_id=sku.sku_id, attribute_id=attr_id, option_id=opt_id))

            m_label = model_value.replace("iPhone ", "")
            s_label = storage_value

            for i in range(item_count):
                roll = random.random()
                if roll < 0.04:  # 내구제/계정거래류 저가 노이즈 — 펜스 필터 검증용
                    price = _price_round(random.uniform(120_000, base_price * 0.55))
                    title = random.choice(JUNK_TITLES).format(m=m_label, s=s_label, n=random.randint(100, 999))
                elif roll < 0.12:  # 미개봉 프리미엄
                    price = _price_round(base_price * random.uniform(1.08, 1.18))
                    title = random.choice(SEALED_TITLES).format(m=m_label, s=s_label)
                else:
                    price = _price_round(random.gauss(base_price, base_price * 0.07))
                    title = random.choice(NORMAL_TITLES).format(m=m_label, s=s_label)

                created = now - timedelta(days=random.uniform(0, DAYS), hours=random.uniform(0, 12))
                source = random.choices(SOURCES, weights=SOURCE_WEIGHTS)[0]
                db.add(Item(
                    sku_id=sku.sku_id,
                    emd_id=random.choice(emd_ids) if random.random() < 0.8 else None,
                    category_id=category_id,
                    title=title,
                    price=price,
                    status=ItemStatus.active,
                    url=f"https://mock.local/{source}/{sku.sku_id}-{i}",
                    source=source,
                    external_id=f"mock-{sku.sku_id}-{i}",
                    created_at=created,
                    updated_at=now,  # 크롤 upsert가 매일 갱신하는 실서비스 동작 재현
                ))
                total_items += 1

            # 지난 4주 일별 스냅샷 — 완만한 드리프트 + 노이즈
            stat_emds = random.sample(emd_ids, k=min(8, len(emd_ids)))
            for day in range(DAYS, -1, -1):
                bucket = datetime.combine((now - timedelta(days=day)).date(), time.min)
                drift = 1 + 0.05 * math.sin((DAYS - day) / 6.5) - 0.0012 * (DAYS - day)
                for emd_id in stat_emds:
                    n = random.randint(2, 9)
                    avg = base_price * drift * random.uniform(0.97, 1.03)
                    db.add(PriceStats(
                        sku_id=sku.sku_id,
                        emd_id=emd_id,
                        bucket_ts=bucket,
                        items_num=n,
                        sum_price=int(avg * n),
                        avg_price=round(avg, 2),
                        min_price=_price_round(avg * 0.88),
                        max_price=_price_round(avg * 1.12),
                    ))
                    total_stats += 1

            await db.commit()
            print(f"SKU {sku.sku_id} {fingerprint} — 매물 {item_count}개")

        print(f"완료: 매물 {total_items}개, price_stats {total_stats}행")


if __name__ == "__main__":
    asyncio.run(main())
