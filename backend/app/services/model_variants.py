"""모델별 실제 판매 스펙(용량·색상) 정적 카탈로그.

검색 드롭다운에서 선택한 모델에 실제로 존재하는 용량/색상만 노출하기 위한
데이터. 키(모델)와 값(옵션)은 seed_catalog의 attribute_option.value 문자열과
정확히 일치해야 한다 — 불일치하면 해당 옵션이 화면에서 사라지므로 주의.
"""

_TITANIUM_16 = ["블랙 티타늄", "화이트 티타늄", "내추럴 티타늄", "데저트 티타늄"]
_TITANIUM_15 = ["블랙 티타늄", "화이트 티타늄", "블루 티타늄", "내추럴 티타늄"]

IPHONE_VARIANTS: dict[str, dict[str, list[str]]] = {
    "iPhone 17 Pro Max": {
        "storage": ["256GB", "512GB", "1TB", "2TB"],
        "color": ["코스믹 오렌지", "딥블루", "실버"],
    },
    "iPhone 17 Pro": {
        "storage": ["256GB", "512GB", "1TB"],
        "color": ["코스믹 오렌지", "딥블루", "실버"],
    },
    "iPhone 17": {
        "storage": ["256GB", "512GB"],
        "color": ["라벤더", "미스트블루", "세이지", "화이트", "블랙"],
    },
    "iPhone 17e": {
        "storage": ["128GB", "256GB", "512GB"],
        "color": ["블랙", "화이트"],
    },
    "iPhone Air": {
        "storage": ["256GB", "512GB", "1TB"],
        "color": ["스페이스 블랙", "클라우드 화이트", "라이트 골드", "스카이 블루"],
    },
    "iPhone 16 Pro Max": {
        "storage": ["256GB", "512GB", "1TB"],
        "color": _TITANIUM_16,
    },
    "iPhone 16 Pro": {
        "storage": ["128GB", "256GB", "512GB", "1TB"],
        "color": _TITANIUM_16,
    },
    "iPhone 16 +": {
        "storage": ["128GB", "256GB", "512GB"],
        "color": ["블랙", "화이트", "핑크", "틸", "울트라마린"],
    },
    "iPhone 16": {
        "storage": ["128GB", "256GB", "512GB"],
        "color": ["블랙", "화이트", "핑크", "틸", "울트라마린"],
    },
    "iPhone 16e": {
        "storage": ["128GB", "256GB", "512GB"],
        "color": ["블랙", "화이트"],
    },
    "iPhone 15 Pro Max": {
        "storage": ["256GB", "512GB", "1TB"],
        "color": _TITANIUM_15,
    },
    "iPhone 15 Pro": {
        "storage": ["128GB", "256GB", "512GB", "1TB"],
        "color": _TITANIUM_15,
    },
    "iPhone 15 +": {
        "storage": ["128GB", "256GB", "512GB"],
        "color": ["블랙", "블루", "그린", "옐로", "핑크"],
    },
    "iPhone 15": {
        "storage": ["128GB", "256GB", "512GB"],
        "color": ["블랙", "블루", "그린", "옐로", "핑크"],
    },
    "iPhone 14 Pro Max": {
        "storage": ["128GB", "256GB", "512GB", "1TB"],
        "color": ["스페이스 블랙", "실버", "골드", "딥 퍼플"],
    },
    "iPhone 14 Pro": {
        "storage": ["128GB", "256GB", "512GB", "1TB"],
        "color": ["스페이스 블랙", "실버", "골드", "딥 퍼플"],
    },
    "iPhone 14+": {
        "storage": ["128GB", "256GB", "512GB"],
        "color": ["미드나이트", "스타라이트", "블루", "퍼플", "옐로", "레드"],
    },
    "iPhone 14": {
        "storage": ["128GB", "256GB", "512GB"],
        "color": ["미드나이트", "스타라이트", "블루", "퍼플", "옐로", "레드"],
    },
    "iPhone SE 3": {
        "storage": ["64GB", "128GB", "256GB"],
        "color": ["미드나이트", "스타라이트", "레드"],
    },
    "iPhone 13 Pro Max": {
        "storage": ["128GB", "256GB", "512GB", "1TB"],
        "color": ["그래파이트", "골드", "실버", "시에라블루", "알파인그린"],
    },
    "iPhone 13 Pro": {
        "storage": ["128GB", "256GB", "512GB", "1TB"],
        "color": ["그래파이트", "골드", "실버", "시에라블루", "알파인그린"],
    },
    "iPhone 13": {
        "storage": ["128GB", "256GB", "512GB"],
        "color": ["미드나이트", "스타라이트", "블루", "핑크", "그린", "레드"],
    },
    "iPhone 13 Mini": {
        "storage": ["128GB", "256GB", "512GB"],
        "color": ["미드나이트", "스타라이트", "블루", "핑크", "그린", "레드"],
    },
    "iPhone 12 Pro Max": {
        "storage": ["128GB", "256GB", "512GB"],
        "color": ["그래파이트", "실버", "골드", "퍼시픽블루"],
    },
    "iPhone 12 Pro": {
        "storage": ["128GB", "256GB", "512GB"],
        "color": ["그래파이트", "실버", "골드", "퍼시픽블루"],
    },
    "iPhone 12 Mini": {
        "storage": ["64GB", "128GB", "256GB"],
        "color": ["블랙", "화이트", "레드", "그린", "블루", "퍼플"],
    },
    "iPhone 12": {
        "storage": ["64GB", "128GB", "256GB"],
        "color": ["블랙", "화이트", "레드", "그린", "블루", "퍼플"],
    },
}

# 카테고리명 → (변형을 결정하는 속성 code, 모델값 → 허용 옵션 맵)
VARIANTS_BY_CATEGORY: dict[str, tuple[str, dict[str, dict[str, list[str]]]]] = {
    "iPhone": ("model", IPHONE_VARIANTS),
}
