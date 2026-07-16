"""추출된 속성을 item_attribute_value에 적재하고 SKU를 생성·연결한다. (plan.md Phase 2)

사용법:
    assigner = SkuAssigner()
    await assigner.load(db)          # 카테고리/속성/옵션/기존 SKU 캐시 (1회)
    await assigner.assign(db, item)  # item마다 호출 — flush된 item_id 필요
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.category import Attribute, AttributeOption, Category, CategoryAttribute
from app.db.models.item import Item, ItemAttributeValue, ItemStatus
from app.db.models.sku import SKU, SKUAttribute
from app.services.attribute_extractor import Extraction, extract, fingerprint

logger = logging.getLogger(__name__)


class SkuAssigner:
    def __init__(self) -> None:
        # category_name → category_id
        self._category_ids: dict[str, int] = {}
        # category_name → {attr_code → (attribute_id, {옵션값 → option_id})}
        self._attributes: dict[str, dict[str, tuple[int, dict[str, int]]]] = {}
        # fingerprint → sku_id
        self._sku_cache: dict[str, int] = {}
        self._loaded = False

    async def load(self, db: AsyncSession) -> None:
        rows = (
            await db.execute(
                select(Category.name, Attribute.code, Attribute.attribute_id, Category.category_id)
                .select_from(CategoryAttribute)
                .join(Category, Category.category_id == CategoryAttribute.category_id)
                .join(Attribute, Attribute.attribute_id == CategoryAttribute.attribute_id)
            )
        ).all()
        option_rows = (
            await db.execute(select(AttributeOption.attribute_id, AttributeOption.value, AttributeOption.option_id))
        ).all()
        options_by_attr: dict[int, dict[str, int]] = {}
        for attribute_id, value, option_id in option_rows:
            options_by_attr.setdefault(attribute_id, {})[value] = option_id

        for category_name, code, attribute_id, category_id in rows:
            self._category_ids[category_name] = category_id
            self._attributes.setdefault(category_name, {})[code] = (
                attribute_id,
                options_by_attr.get(attribute_id, {}),
            )

        sku_rows = (await db.execute(select(SKU.fingerprint, SKU.sku_id))).all()
        self._sku_cache = {fp: sku_id for fp, sku_id in sku_rows}
        self._loaded = True

    async def assign(self, db: AsyncSession, item: Item) -> Extraction | None:
        """item의 속성을 적재하고 가능하면 SKU를 연결한다. item은 flush된 상태여야 한다."""
        assert self._loaded, "SkuAssigner.load()를 먼저 호출해야 한다"

        extraction = extract(item.title, item.search_keyword)
        if extraction is None:
            return None

        category_name = extraction.category
        attr_defs = self._attributes.get(category_name)
        if not attr_defs:
            logger.warning("속성 정의가 없는 카테고리: %s (시드 누락?)", category_name)
            return extraction

        if extraction.is_sold and item.status == ItemStatus.active:
            item.status = ItemStatus.sold

        # 노이즈(필터 재검증 실패)는 속성도 적재하지 않는다
        if not extraction.title_matches_target:
            return extraction

        for code, value in extraction.attributes.items():
            definition = attr_defs.get(code)
            if definition is None:
                logger.warning("시드에 없는 속성 코드: %s.%s", category_name, code)
                continue
            attribute_id, option_ids = definition
            option_id = option_ids.get(value)
            if option_id is None:
                logger.warning("시드에 없는 옵션값: %s.%s=%r", category_name, code, value)
                continue
            statement = mysql_insert(ItemAttributeValue).values(
                item_id=item.item_id,
                attribute_id=attribute_id,
                option_id=option_id,
                value_text=value,
            )
            statement = statement.on_duplicate_key_update(
                option_id=statement.inserted.option_id,
                value_text=statement.inserted.value_text,
            )
            await db.execute(statement)

        if extraction.sku_ready:
            sku_id = await self._get_or_create_sku(db, extraction)
            if sku_id is not None:
                item.sku_id = sku_id
        return extraction

    async def _get_or_create_sku(self, db: AsyncSession, extraction: Extraction) -> int | None:
        category_id = self._category_ids.get(extraction.category)
        if category_id is None:
            return None
        fp = fingerprint(category_id, extraction)
        cached = self._sku_cache.get(fp)
        if cached is not None:
            return cached

        existing = (await db.execute(select(SKU.sku_id).where(SKU.fingerprint == fp))).scalar_one_or_none()
        if existing is not None:
            self._sku_cache[fp] = existing
            return existing

        sku = SKU(category_id=category_id, fingerprint=fp)
        db.add(sku)
        await db.flush()
        attr_defs = self._attributes[extraction.category]
        for code in extraction.required_codes:
            attribute_id, option_ids = attr_defs[code]
            value = extraction.attributes[code]
            db.add(
                SKUAttribute(
                    sku_id=sku.sku_id,
                    attribute_id=attribute_id,
                    option_id=option_ids.get(value),
                    value_text=value,
                )
            )
        self._sku_cache[fp] = sku.sku_id
        return sku.sku_id
