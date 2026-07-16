"""매물 제목 + 검색 키워드에서 카테고리 속성값을 추출한다. (plan.md Phase 1)

설계 원칙:
- 모델 속성은 제목을 파싱하지 않는다. filters.matches_target_title()이 크롤링 시점에
  제목-타깃 일치를 강제하므로, search_keyword → CrawlTarget 역매핑만으로 모델이 확정된다.
- 반환하는 속성값은 반드시 seed_catalog.py에 시드된 attribute_option 값 문자열이다.
  (스냅 실패 시 해당 속성을 누락시킨다 — 틀린 값보다 빈 값이 낫다.)
- 단위 없는 숫자는 {64, 128, 256, 512} 화이트리스트에 있을 때만 용량으로 인정하고,
  배터리 성능 표기("배터리 88%", "성능 100퍼")는 위치 기반 가드로 배제한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.crawlers.filters import matches_target_title
from app.crawlers.targets import CRAWL_TARGETS, CrawlTarget


# ---------------------------------------------------------------------------
# search_keyword → CrawlTarget 역매핑
# ---------------------------------------------------------------------------

def _build_keyword_map() -> dict[str, CrawlTarget]:
    mapping: dict[str, CrawlTarget] = {}
    for target in CRAWL_TARGETS:
        for keyword in target.keywords:
            existing = mapping.get(keyword)
            if existing is not None and existing is not target:
                raise ValueError(f"두 타깃이 같은 검색 키워드를 사용: {keyword!r}")
            mapping[keyword] = target
    return mapping


KEYWORD_TO_TARGET: dict[str, CrawlTarget] = _build_keyword_map()


# ---------------------------------------------------------------------------
# target.model → 시드된 모델 옵션값 매핑
# (표기가 동일하면 생략 — resolve_model_option()이 target.model을 그대로 쓴다)
# ---------------------------------------------------------------------------

_IPHONE_MODEL_OPTION = {
    "iPhone SE 3rd generation": "iPhone SE 3",
    "iPhone 14 Plus": "iPhone 14+",
    "iPhone 15 Plus": "iPhone 15 +",
    "iPhone 16 Plus": "iPhone 16 +",
}

_IPAD_MODEL_OPTION = {
    "iPad Air 5th generation": "아이패드 에어 5세대",
    "iPad 10th generation": "아이패드 10세대",
    "iPad Pro 11-inch 4th generation": "아이패드 프로 11 4세대",
    "iPad Pro 12.9-inch 6th generation": "아이패드 프로 12.9 6세대",
    "iPad Air 11-inch M2": "아이패드 에어 11 (M2)",
    "iPad Air 13-inch M2": "아이패드 에어 13 (M2)",
    "iPad Pro 11-inch M4": "아이패드 프로 11 M4",
    "iPad Pro 13-inch M4": "아이패드 프로 13 M4",
    "iPad mini A17 Pro": "아이패드 미니 A17Pro",
    "iPad A16": "아이패드 (A16)",
    "iPad Air 11-inch M3": "아이패드 에어 11 (M3)",
    "iPad Air 13-inch M3": "아이패드 에어 13 (M3)",
}

_WATCH_MODEL_OPTION = {
    "Apple Watch Series 8": "워치8",
    "Apple Watch Series 9": "워치9",
    "Apple Watch Series 10": "워치10",
    "Apple Watch Series 11": "워치11",
    "Apple Watch SE 2nd generation": "워치 SE2",
    "Apple Watch SE 3rd generation": "워치 SE3",
    "Apple Watch Ultra": "워치 울트라",
    "Apple Watch Ultra 2": "워치 울트라2",
    "Apple Watch Ultra 3": "워치 울트라3",
}

_AIRPODS_MODEL_OPTION = {
    "AirPods Pro 2nd generation": "에어팟 프로 2세대",
    # USB-C 리비전은 시드 옵션에 구분이 없어 같은 세대로 합친다 (시세 차이 미미)
    "AirPods Pro 2nd generation USB-C": "에어팟 프로 2세대",
    "AirPods 4": "에어팟 4세대",
    "AirPods 4 ANC": "에어팟 4세대 노이즈캔슬링",
    "AirPods Max USB-C": "에어팟 맥스",
    "AirPods Pro 3rd generation": "에어팟 프로 3세대",
}

# "MacBook Pro 14-inch M4 Pro" → (맥북 프로, 14인치, M4 Pro)
_MACBOOK_MODEL_RE = re.compile(r"^MacBook (Air|Pro) (\d{2})-inch (M\d(?: Pro| Max)?)$")

# SKU fingerprint에 들어가는 속성 (plan.md 3-2 — 순서 고정)
REQUIRED_CODES: dict[str, tuple[str, ...]] = {
    "iPhone": ("model", "storage"),
    "iPad": ("ipad_model", "ipad_storage"),
    "MacBook": ("macbook_model", "macbook_chipset", "macbook_display", "macbook_ram", "macbook_ssd"),
    "AppleWatch": ("watch_model", "watch_size"),
    "AirPods": ("airpods_model",),
}


# ---------------------------------------------------------------------------
# 용량 추출
# ---------------------------------------------------------------------------

_UNIT_GB_RE = re.compile(r"(\d{2,4})\s*(?:gb|기가|giga|g(?![a-z]))", re.I)
_UNIT_TB_RE = re.compile(r"([1248])\s*(?:tb|테라)", re.I)
_BARE_STORAGE_RE = re.compile(r"(?<![\d.])(64|128|256|512)(?![\d%])")
_STORAGE_TYPO = {516: 512, 254: 256}

_IPHONE_STORAGE = {64: "64GB", 128: "128GB", 256: "256GB", 512: "512GB"}
_IPHONE_TB = {1: "1TB", 2: "2TB"}
_IPAD_STORAGE = {32: "32GB", **_IPHONE_STORAGE}


def _bare_number_guarded(lower: str, match: re.Match) -> bool:
    """'배터리 88', '성능 100', '256%' 류의 숫자를 용량으로 오인하지 않게 막는다."""
    start, end = match.start(1), match.end(1)
    before = lower[max(0, start - 8):start]
    after = lower[end:end + 2]
    if "배터리" in before or "성능" in before:
        return True
    if after.startswith(("%", "퍼")):
        return True
    return False


def _extract_storage(title: str, gb_options: dict[int, str], tb_options: dict[int, str]) -> str | None:
    lower = title.lower()
    tb = _UNIT_TB_RE.search(lower)
    if tb:
        return tb_options.get(int(tb.group(1)))
    for m in _UNIT_GB_RE.finditer(lower):
        value = int(m.group(1))
        value = _STORAGE_TYPO.get(value, value)
        if value in gb_options:
            return gb_options[value]
    for m in _BARE_STORAGE_RE.finditer(lower):
        if _bare_number_guarded(lower, m):
            continue
        return gb_options[int(m.group(1))]
    return None


# ---------------------------------------------------------------------------
# 색상 추출 (compact 비교, 긴 이름 우선 — '블랙 티타늄'이 '블랙'보다 먼저)
# ---------------------------------------------------------------------------

_COLOR_SYNONYMS = {"미드나잇": "미드나이트", "옐로우": "옐로"}

_IPHONE_COLORS = (
    "실버", "그래파이트", "골드", "퍼시픽블루", "블랙", "화이트", "레드", "그린", "블루",
    "퍼플", "시에라블루", "알파인그린", "스타라이트", "미드나이트", "핑크", "스페이스 블랙",
    "딥 퍼플", "옐로", "블랙 티타늄", "화이트 티타늄", "블루 티타늄", "내추럴 티타늄",
    "데저트 티타늄", "틸", "울트라마린", "코스믹 오렌지", "딥블루", "미스트블루", "세이지",
    "라벤더", "클라우드 화이트", "라이트 골드", "스카이 블루",
)

_MACBOOK_COLORS = ("스페이스 그레이", "실버", "미드나이트", "스타라이트", "골드", "로즈 골드", "스페이스 블랙", "스카이 블루")


def _compact(value: str) -> str:
    normalized = value.lower().replace("+", "plus")
    return re.sub(r"[\W_]+", "", normalized)


def _build_color_matcher(options: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    entries: list[tuple[str, str]] = [(_compact(option), option) for option in options]
    for alias, canonical in _COLOR_SYNONYMS.items():
        if canonical in options:
            entries.append((_compact(alias), canonical))
    entries.sort(key=lambda pair: len(pair[0]), reverse=True)
    return tuple(entries)


_IPHONE_COLOR_MATCHER = _build_color_matcher(_IPHONE_COLORS)
_MACBOOK_COLOR_MATCHER = _build_color_matcher(_MACBOOK_COLORS)


def _extract_color(title: str, matcher: tuple[tuple[str, str], ...]) -> str | None:
    compact = _compact(title)
    for compact_option, option in matcher:
        if compact_option in compact:
            return option
    return None


# ---------------------------------------------------------------------------
# 카테고리별 나머지 속성
# ---------------------------------------------------------------------------

_CELLULAR_RE = re.compile(r"셀룰러|셀루러|cellular|lte", re.I)
_WIFI_RE = re.compile(r"wi-?fi|와이파이|wifi", re.I)
_GPS_RE = re.compile(r"\bgps\b|지피에스", re.I)
_WATCH_MM_RE = re.compile(r"(40|41|42|44|45|46|49)\s*(?:mm|미리|밀리)", re.I)

_MACBOOK_RAM_GB = {8, 16, 18, 24, 32, 36, 48, 64, 96, 128}
_MACBOOK_SSD_GB = {256, 512}
_MACBOOK_SSD_TB = {1, 2, 4, 8}

# filters._matches_macbook은 에어/프로와 칩셋만 검증하고 인치는 검증하지 않아서
# 14인치 타깃 검색에 16인치 매물이 섞인다 → 인치는 제목에서 우선 추출한다.
_MACBOOK_INCH_RE = re.compile(r"(1[3-6])\s*(?:인치|inch|\")|(?:프로|에어|pro|air)\s*(1[3-6])(?!\d)", re.I)
_MACBOOK_VALID_INCH = {"Air": {"13", "15"}, "Pro": {"13", "14", "16"}}


def _extract_macbook_display(title: str, line: str, target_inch: str) -> str:
    m = _MACBOOK_INCH_RE.search(title)
    if m:
        inch = m.group(1) or m.group(2)
        if inch in _MACBOOK_VALID_INCH[line]:
            return f"{inch}인치"
    return f"{target_inch}인치"


def _extract_macbook_memory(title: str) -> tuple[str | None, str | None]:
    """제목의 GB/TB 숫자들에서 (RAM, SSD)를 판별한다.

    규칙: TB는 무조건 SSD. GB는 96 이하이면 RAM, 256 이상이면 SSD.
    128GB는 양쪽 다 될 수 있어 SSD가 따로 확정된 경우에만 RAM으로 인정한다.
    """
    lower = title.lower()
    ram: str | None = None
    ssd: str | None = None
    saw_128 = False

    for m in _UNIT_TB_RE.finditer(lower):
        value = int(m.group(1))
        if value in _MACBOOK_SSD_TB and ssd is None:
            ssd = f"{value}TB"

    for m in _UNIT_GB_RE.finditer(lower):
        value = int(m.group(1))
        value = _STORAGE_TYPO.get(value, value)
        if value == 128:
            saw_128 = True
        elif value <= 96:
            if value in _MACBOOK_RAM_GB and ram is None:
                ram = f"{value}GB"
        elif value in _MACBOOK_SSD_GB and ssd is None:
            ssd = f"{value}GB"

    if saw_128 and ram is None and ssd is not None:
        ram = "128GB"
    return ram, ssd


def _extract_watch_material(title: str) -> str | None:
    compact = _compact(title)
    if "스테인리스" in compact:
        return "스테인리스스틸"
    if "티타늄" in compact:
        return "티타늄"
    if "알루미늄" in compact or "알미늄" in compact:
        return "알루미늄"
    return None


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

DAMAGE_RE = re.compile(r"파손|깨짐|부품용|고장|하자|수리용|잔상")
SOLD_RE = re.compile(r"거래\s*완료|판매\s*완료|예약\s*중|예약\s*완료")
# 에르메스 에디션은 일반 모델 대비 가격이 수 배라 SKU 시세를 왜곡한다 (filters.py 가격 상한 주석 참조)
SPECIAL_EDITION_RE = re.compile(r"에르메스|hermes", re.I)


@dataclass
class Extraction:
    target: CrawlTarget
    attributes: dict[str, str] = field(default_factory=dict)  # attr code → 시드 옵션값
    title_matches_target: bool = True
    is_damaged: bool = False
    is_sold: bool = False
    is_special_edition: bool = False

    @property
    def category(self) -> str:
        return self.target.category

    @property
    def required_codes(self) -> tuple[str, ...]:
        return REQUIRED_CODES[self.target.category]

    @property
    def sku_ready(self) -> bool:
        """SKU 배정 가능 여부 — 노이즈/파손 매물은 시세를 왜곡하므로 제외한다."""
        if not self.title_matches_target or self.is_damaged or self.is_special_edition:
            return False
        return all(code in self.attributes for code in self.required_codes)


def resolve_target(search_keyword: str | None) -> CrawlTarget | None:
    if not search_keyword:
        return None
    return KEYWORD_TO_TARGET.get(search_keyword)


def resolve_model_option(target: CrawlTarget) -> str:
    if target.category == "iPhone":
        return _IPHONE_MODEL_OPTION.get(target.model, target.model)
    if target.category == "iPad":
        return _IPAD_MODEL_OPTION[target.model]
    if target.category == "AppleWatch":
        return _WATCH_MODEL_OPTION[target.model]
    if target.category == "AirPods":
        return _AIRPODS_MODEL_OPTION[target.model]
    raise ValueError(f"모델 옵션 매핑이 없는 카테고리: {target.category}")


def extract(title: str, search_keyword: str | None) -> Extraction | None:
    """제목+검색어에서 속성을 추출한다. 타깃을 못 찾으면 None."""
    target = resolve_target(search_keyword)
    if target is None:
        return None

    extraction = Extraction(
        target=target,
        title_matches_target=matches_target_title(title, target),
        is_damaged=bool(DAMAGE_RE.search(title)),
        is_sold=bool(SOLD_RE.search(title)),
        is_special_edition=bool(SPECIAL_EDITION_RE.search(title)),
    )
    attrs = extraction.attributes
    category = target.category

    if category == "iPhone":
        attrs["model"] = resolve_model_option(target)
        storage = _extract_storage(title, _IPHONE_STORAGE, _IPHONE_TB)
        if storage:
            attrs["storage"] = storage
        color = _extract_color(title, _IPHONE_COLOR_MATCHER)
        if color:
            attrs["color"] = color

    elif category == "iPad":
        attrs["ipad_model"] = resolve_model_option(target)
        storage = _extract_storage(title, _IPAD_STORAGE, _IPHONE_TB)
        if storage:
            attrs["ipad_storage"] = storage
        if _CELLULAR_RE.search(title):
            attrs["ipad_connection"] = "Wi-Fi + Cellular"
        elif _WIFI_RE.search(title):
            attrs["ipad_connection"] = "Wi-Fi"

    elif category == "MacBook":
        parsed = _MACBOOK_MODEL_RE.match(target.model)
        if parsed:
            line, inch, chipset = parsed.groups()
            attrs["macbook_model"] = "맥북 에어" if line == "Air" else "맥북 프로"
            attrs["macbook_display"] = _extract_macbook_display(title, line, inch)
            attrs["macbook_chipset"] = chipset
        ram, ssd = _extract_macbook_memory(title)
        if ram:
            attrs["macbook_ram"] = ram
        if ssd:
            attrs["macbook_ssd"] = ssd
        color = _extract_color(title, _MACBOOK_COLOR_MATCHER)
        if color:
            attrs["macbook_color"] = color

    elif category == "AppleWatch":
        attrs["watch_model"] = resolve_model_option(target)
        mm = _WATCH_MM_RE.search(title)
        if mm:
            attrs["watch_size"] = f"{mm.group(1)}mm"
        if _CELLULAR_RE.search(title):
            attrs["watch_connection"] = "GPS + 셀룰러"
        elif _GPS_RE.search(title):
            attrs["watch_connection"] = "GPS"
        material = _extract_watch_material(title)
        if material:
            attrs["watch_material"] = material

    elif category == "AirPods":
        attrs["airpods_model"] = resolve_model_option(target)

    return extraction


def fingerprint(category_id: int, extraction: Extraction) -> str:
    """SKU 식별자 — category_id + required 속성 조합 (plan.md 3-2)."""
    parts = "|".join(f"{code}={extraction.attributes[code]}" for code in extraction.required_codes)
    return f"{category_id}:{parts}"
