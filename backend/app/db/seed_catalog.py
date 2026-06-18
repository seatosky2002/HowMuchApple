import asyncio

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.category import Attribute, AttributeDatatype, AttributeOption, Category, CategoryAttribute
from app.db.session import AsyncSessionLocal, engine


CATALOG = [
    {
        "name": "iPhone",
        "attributes": [
            {
                "code": "model",
                "label": "모델",
                "required": True,
                "options": [
                    "iPhone 17 Pro Max",
                    "iPhone 17 Pro",
                    "iPhone 17",
                    "iPhone Air",
                    "iPhone 16 Pro Max",
                    "iPhone 16 Pro",
                    "iPhone 16 +",
                    "iPhone 16",
                    "iPhone 16e",
                    "iPhone 15 Pro Max",
                    "iPhone 15 Pro",
                    "iPhone 15 +",
                    "iPhone 15",
                    "iPhone 14 Pro Max",
                    "iPhone 14 Pro",
                    "iPhone 14+",
                    "iPhone 14",
                    "iPhone 13 Pro Max",
                    "iPhone 13 Pro",
                    "iPhone 13",
                    "iPhone 13 Mini",
                    "iPhone 12 Pro Max",
                    "iPhone 12 Pro",
                    "iPhone 12 Mini",
                    "iPhone 12",
                ],
            },
            {
                "code": "storage",
                "label": "용량",
                "required": True,
                "options": ["64GB", "128GB", "256GB", "512GB", "1TB", "2TB"],
            },
            {
                "code": "color",
                "label": "색상",
                "required": False,
                "options": [
                    "실버",
                    "그래파이트",
                    "골드",
                    "퍼시픽블루",
                    "블랙",
                    "화이트",
                    "레드",
                    "그린",
                    "블루",
                    "퍼플",
                    "시에라블루",
                    "알파인그린",
                    "스타라이트",
                    "미드나이트",
                    "핑크",
                    "스페이스 블랙",
                    "딥 퍼플",
                    "옐로",
                    "블랙 티타늄",
                    "화이트 티타늄",
                    "블루 티타늄",
                    "내추럴 티타늄",
                    "데저트 티타늄",
                    "틸",
                    "울트라마린",
                    "코스믹 오렌지",
                    "딥블루",
                    "미스트블루",
                    "세이지",
                    "라벤더",
                    "클라우드 화이트",
                    "라이트 골드",
                    "스카이 블루",
                ],
            },
        ],
    },
    {
        "name": "iPad",
        "attributes": [
            {
                "code": "ipad_model",
                "label": "모델",
                "required": True,
                "options": [
                    "아이패드 프로 12.9 3세대",
                    "아이패드 프로 11 1세대",
                    "아이패드 프로 12.9 4세대",
                    "아이패드 프로 11 2세대",
                    "아이패드 프로 12.9 5세대",
                    "아이패드 프로 11 3세대",
                    "아이패드 프로 12.9 6세대",
                    "아이패드 프로 11 4세대",
                    "아이패드 프로 13 M4",
                    "아이패드 프로 11 M4",
                    "아이패드 에어 3세대",
                    "아이패드 에어 4세대",
                    "아이패드 에어 5세대",
                    "아이패드 에어 11 (M2)",
                    "아이패드 에어 13 (M2)",
                    "아이패드 에어 11 (M3)",
                    "아이패드 에어 13 (M3)",
                    "아이패드 6세대",
                    "아이패드 7세대",
                    "아이패드 8세대",
                    "아이패드 9세대",
                    "아이패드 10세대",
                    "아이패드 (A16)",
                    "아이패드 미니 5세대",
                    "아이패드 미니 6세대",
                    "아이패드 미니 A17Pro",
                ],
            },
            {
                "code": "ipad_storage",
                "label": "용량",
                "required": True,
                "options": ["32GB", "64GB", "128GB", "256GB", "512GB", "1TB", "2TB"],
            },
            {
                "code": "ipad_connection",
                "label": "연결",
                "required": False,
                "options": ["Wi-Fi", "Wi-Fi + Cellular"],
            },
        ],
    },
    {
        "name": "MacBook",
        "attributes": [
            {
                "code": "macbook_model",
                "label": "모델",
                "required": True,
                "options": ["맥북 에어", "맥북 프로"],
            },
            {
                "code": "macbook_chipset",
                "label": "칩셋",
                "required": True,
                "options": [
                    "M5",
                    "M5 Pro",
                    "M5 Max",
                    "M4",
                    "M4 Pro",
                    "M4 Max",
                    "M3",
                    "M3 Pro",
                    "M3 Max",
                    "M2",
                    "M2 Pro",
                    "M2 Max",
                    "M1",
                    "M1 Pro",
                    "M1 Max",
                    "Intel Core i9",
                    "Intel Core i7",
                    "Intel Core i5",
                    "Intel Core i3",
                ],
            },
            {
                "code": "macbook_ram",
                "label": "메모리",
                "required": True,
                "options": ["8GB", "16GB", "18GB", "24GB", "32GB", "36GB", "48GB", "64GB", "96GB", "128GB"],
            },
            {
                "code": "macbook_ssd",
                "label": "SSD",
                "required": True,
                "options": ["256GB", "512GB", "1TB", "2TB", "4TB", "8TB"],
            },
            {
                "code": "macbook_color",
                "label": "색상",
                "required": False,
                "options": [
                    "스페이스 그레이",
                    "실버",
                    "미드나이트",
                    "스타라이트",
                    "골드",
                    "로즈 골드",
                    "스페이스 블랙",
                    "스카이 블루",
                ],
            },
            {
                "code": "macbook_display",
                "label": "화면",
                "required": False,
                "options": ["13인치", "14인치", "15인치", "16인치"],
            },
        ],
    },
    {
        "name": "AppleWatch",
        "attributes": [
            {
                "code": "watch_model",
                "label": "모델",
                "required": True,
                "options": [
                    "워치 울트라3",
                    "워치 울트라2",
                    "워치 울트라",
                    "워치11",
                    "워치10 에르메스",
                    "워치10",
                    "워치9",
                    "워치8",
                    "워치7 나이키",
                    "워치7",
                    "워치6",
                    "워치 SE3",
                    "워치 SE2",
                    "워치 SE",
                ],
            },
            {
                "code": "watch_size",
                "label": "크기",
                "required": True,
                "options": ["40mm", "41mm", "42mm", "44mm", "45mm", "46mm", "49mm"],
            },
            {
                "code": "watch_material",
                "label": "소재",
                "required": False,
                "options": ["알루미늄", "스테인리스스틸", "티타늄"],
            },
            {
                "code": "watch_connection",
                "label": "연결",
                "required": False,
                "options": ["GPS", "GPS + 셀룰러"],
            },
        ],
    },
    {
        "name": "AirPods",
        "attributes": [
            {
                "code": "airpods_model",
                "label": "모델",
                "required": True,
                "options": [
                    "에어팟 4세대",
                    "에어팟 프로 3세대",
                    "에어팟 3세대",
                    "에어팟 프로 2세대",
                    "에어팟 2세대",
                    "에어팟 프로 1세대",
                    "에어팟 1세대",
                    "에어팟 맥스",
                ],
            }
        ],
    },
]


async def _get_or_create_category(db: AsyncSession, name: str) -> Category:
    category = (await db.execute(select(Category).where(Category.name == name))).scalar_one_or_none()
    if category:
        return category
    category = Category(name=name)
    db.add(category)
    await db.flush()
    return category


async def _get_or_create_attribute(db: AsyncSession, code: str, label: str) -> Attribute:
    attribute = (await db.execute(select(Attribute).where(Attribute.code == code))).scalar_one_or_none()
    if attribute:
        attribute.label = label
        attribute.datatype = AttributeDatatype.option
        return attribute
    attribute = Attribute(code=code, label=label, datatype=AttributeDatatype.option)
    db.add(attribute)
    await db.flush()
    return attribute


async def _get_or_create_option(
    db: AsyncSession,
    attribute_id: int,
    value: str,
    sort_order: int,
) -> AttributeOption:
    option = (
        await db.execute(
            select(AttributeOption).where(
                AttributeOption.attribute_id == attribute_id,
                AttributeOption.value == value,
            )
        )
    ).scalar_one_or_none()
    if option:
        option.sort_order = sort_order
        return option
    option = AttributeOption(attribute_id=attribute_id, value=value, sort_order=sort_order)
    db.add(option)
    return option


async def seed_catalog() -> None:
    async with AsyncSessionLocal() as db:
        for category_sort, category_data in enumerate(CATALOG, start=1):
            category = await _get_or_create_category(db, category_data["name"])
            await db.flush()
            await db.execute(delete(CategoryAttribute).where(CategoryAttribute.category_id == category.category_id))

            for attr_sort, attr_data in enumerate(category_data["attributes"], start=1):
                attribute = await _get_or_create_attribute(db, attr_data["code"], attr_data["label"])
                await db.flush()

                for option_sort, value in enumerate(attr_data["options"], start=1):
                    await _get_or_create_option(db, attribute.attribute_id, value, option_sort)

                db.add(
                    CategoryAttribute(
                        category_id=category.category_id,
                        attribute_id=attribute.attribute_id,
                        is_required=attr_data["required"],
                        display_group="기본 정보",
                        sort_order=attr_sort,
                    )
                )

        await db.commit()

    await engine.dispose()
    print(f"Seeded {len(CATALOG)} Apple categories.")


if __name__ == "__main__":
    asyncio.run(seed_catalog())
