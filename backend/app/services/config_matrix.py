"""칩셋이 실제로 지원하는 RAM/SSD/화면 조합만 통과시키는 검증 매트릭스.

배경: SKU는 "제목에서 뽑은 값 조합"으로 만들어지는데, 칩이 지원하지 않는 값이
제목 노이즈로 섞여 존재하지 않는 SKU가 생긴다. 대표 사례 —
- "M5 Pro 16코어 GPU"의 16이 RAM(16GB)으로 오인 → 실제로 M5 Pro 최소 RAM은 24GB
- Pro/Max 칩에 256GB SSD (해당 칩 최소 512GB~2TB)

그래서 (모델, 칩셋)마다 애플이 실제 판매하는 화면/RAM/SSD 집합을 고정하고,
그 밖의 값은 파싱 오류로 간주해 버린다. 출처: Apple 공식 사양 + EveryMac CTO 정리
(2026-08 확인). 문자열은 seed_catalog.py의 attribute_option 값과 정확히 일치해야 한다.
"""

from __future__ import annotations

_AIR = "맥북 에어"
_PRO = "맥북 프로"

# (macbook_model, macbook_chipset) → {"display", "ram", "ssd"} 각 허용 집합.
# RAM은 96 이하가 base/Pro/Max를 구분하는 핵심 축(사용자 요청의 "칩이 지원하는 랩").
MACBOOK_CONFIGS: dict[tuple[str, str], dict[str, frozenset[str]]] = {
    # --- MacBook Air (base 칩만) ---
    (_AIR, "M2"): {"display": {"13인치", "15인치"}, "ram": {"8GB", "16GB", "24GB"}, "ssd": {"256GB", "512GB", "1TB", "2TB"}},
    (_AIR, "M3"): {"display": {"13인치", "15인치"}, "ram": {"8GB", "16GB", "24GB"}, "ssd": {"256GB", "512GB", "1TB", "2TB"}},
    (_AIR, "M4"): {"display": {"13인치", "15인치"}, "ram": {"16GB", "24GB", "32GB"}, "ssd": {"256GB", "512GB", "1TB", "2TB"}},
    # --- MacBook Pro ---
    (_PRO, "M2"): {"display": {"13인치"}, "ram": {"8GB", "16GB", "24GB"}, "ssd": {"256GB", "512GB", "1TB", "2TB"}},
    (_PRO, "M2 Pro"): {"display": {"14인치", "16인치"}, "ram": {"16GB", "32GB"}, "ssd": {"512GB", "1TB", "2TB", "4TB", "8TB"}},
    (_PRO, "M2 Max"): {"display": {"14인치", "16인치"}, "ram": {"32GB", "64GB", "96GB"}, "ssd": {"1TB", "2TB", "4TB", "8TB"}},
    (_PRO, "M3"): {"display": {"14인치"}, "ram": {"8GB", "16GB", "24GB"}, "ssd": {"512GB", "1TB", "2TB"}},
    (_PRO, "M3 Pro"): {"display": {"14인치", "16인치"}, "ram": {"18GB", "36GB"}, "ssd": {"512GB", "1TB", "2TB", "4TB"}},
    (_PRO, "M3 Max"): {"display": {"14인치", "16인치"}, "ram": {"36GB", "48GB", "64GB", "96GB", "128GB"}, "ssd": {"1TB", "2TB", "4TB", "8TB"}},
    (_PRO, "M4"): {"display": {"14인치"}, "ram": {"16GB", "24GB", "32GB"}, "ssd": {"512GB", "1TB", "2TB"}},
    (_PRO, "M4 Pro"): {"display": {"14인치", "16인치"}, "ram": {"24GB", "48GB"}, "ssd": {"512GB", "1TB", "2TB", "4TB"}},
    (_PRO, "M4 Max"): {"display": {"14인치", "16인치"}, "ram": {"36GB", "48GB", "64GB", "128GB"}, "ssd": {"1TB", "2TB", "4TB", "8TB"}},
    (_PRO, "M5"): {"display": {"14인치"}, "ram": {"16GB", "24GB", "32GB"}, "ssd": {"512GB", "1TB", "2TB", "4TB"}},
    (_PRO, "M5 Pro"): {"display": {"14인치", "16인치"}, "ram": {"24GB", "48GB", "64GB"}, "ssd": {"1TB", "2TB", "4TB", "8TB"}},
    (_PRO, "M5 Max"): {"display": {"14인치", "16인치"}, "ram": {"36GB", "48GB", "64GB", "128GB"}, "ssd": {"2TB", "4TB", "8TB"}},
}

_DIM_TO_CODE = {"macbook_display": "display", "macbook_ram": "ram", "macbook_ssd": "ssd"}


def macbook_allows(model: str | None, chipset: str | None, code: str, value: str) -> bool:
    """(모델, 칩셋)에 대해 code(=macbook_ram 등) 값이 실존 조합인지.

    매트릭스에 없는 (모델, 칩셋)(예: M1/Intel 등 미크롤 조합)은 검증하지 않고
    통과시킨다 — 아는 것만 거른다.
    """
    spec = MACBOOK_CONFIGS.get((model, chipset))
    if spec is None:
        return True
    dim = _DIM_TO_CODE.get(code)
    if dim is None:
        return True
    return value in spec[dim]


def is_valid_macbook(attrs: dict[str, str]) -> bool:
    """RAM/SSD/화면이 모두 (모델, 칩셋)의 실존 조합에 속하는지."""
    model = attrs.get("macbook_model")
    chipset = attrs.get("macbook_chipset")
    spec = MACBOOK_CONFIGS.get((model, chipset))
    if spec is None:
        return True
    for code, dim in _DIM_TO_CODE.items():
        value = attrs.get(code)
        if value is not None and value not in spec[dim]:
            return False
    return True


def is_valid_config(category: str, attrs: dict[str, str]) -> bool:
    """카테고리별 조합 유효성. 현재 MacBook만 칩셋 제약이 있다."""
    if category == "MacBook":
        return is_valid_macbook(attrs)
    return True
