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
from app.services.config_matrix import is_valid_config, macbook_allows


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
# "1T", "2t" 처럼 T만 쓰는 표기도 흔하다(실측 78건). 다만 "2티어" 류를 피하려고
# 뒤에 영문·한글이 붙는 경우는 배제한다.
_UNIT_TB_RE = re.compile(r"([1248])\s*(?:tb|테라|t(?![a-zA-Z가-힣]))", re.I)
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

# 맥북 RAM은 한 자리(8GB)가 흔하다. 공용 _UNIT_GB_RE는 아이폰/아이패드 용량용으로
# 두 자리 이상만 받으므로(단위 없는 "5g" 류 오탐 방지) 맥북 전용 패턴을 따로 둔다.
# 값 화이트리스트(_MACBOOK_RAM_GB/_SSD_GB)가 최종 가드라서 한 자리를 허용해도 안전하다.
_MACBOOK_GB_RE = re.compile(r"(?<!\d)(?<!\d\.)(\d{1,4})\s*(?:gb|기가|giga|g(?![a-z]))", re.I)

# 단위 없는 "16/256", "8+256", "24/512", 인치까지 붙은 "14/48/1tb" 표기를 받는다.
# 실데이터에서 맥북 미배정분의 상당수가 이 형태였다.
_MACBOOK_COMBO_RE = re.compile(
    r"(?<!\d)(?<!\d\.)(\d{1,4})\s*(gb|기가|tb|테라|g)?\s*[/+,]\s*(\d{1,4})\s*(gb|기가|tb|테라|g)?"
    r"(?:\s*[/+,]\s*(\d{1,4})\s*(gb|기가|tb|테라|g)?)?",
    re.I,
)

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
    단위가 붙은 표기를 먼저 보고, 못 채운 값만 단위 없는 조합 표기에서 보충한다.
    """
    lower = title.lower()
    ram: str | None = None
    ssd: str | None = None
    saw_128 = False

    for m in _UNIT_TB_RE.finditer(lower):
        value = int(m.group(1))
        if value in _MACBOOK_SSD_TB and ssd is None:
            ssd = f"{value}TB"

    for m in _MACBOOK_GB_RE.finditer(lower):
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

    if ram is None or ssd is None:
        combo_ram, combo_ssd = _extract_macbook_combo(lower)
        ram = ram or combo_ram
        ssd = ssd or combo_ssd
    if ram is None or ssd is None:
        spaced_ram, spaced_ssd = _extract_macbook_spaced(lower)
        ram = ram or spaced_ram
        ssd = ssd or spaced_ssd
    return ram, ssd


# 구분자 없이 공백만으로 쓴 "16 512" 표기. 숫자 나열이 흔한 제목에서 오탐이 쉬워
# RAM·SSD 화이트리스트를 둘 다 만족할 때만 인정하고, 배터리/사이클 문맥은 배제한다.
_MACBOOK_SPACED_RE = re.compile(r"(?<!\d)(?<!\d\.)(\d{1,3})\s+(\d{3,4})(?!\d)")
_SPACED_GUARD_RE = re.compile(r"(배터리|성능|사이클|cycle)\s*$", re.I)


def _extract_macbook_spaced(lower: str) -> tuple[str | None, str | None]:
    for m in _MACBOOK_SPACED_RE.finditer(lower):
        if _SPACED_GUARD_RE.search(lower[max(0, m.start() - 12):m.start()]):
            continue
        ram_v = _STORAGE_TYPO.get(int(m.group(1)), int(m.group(1)))
        ssd_v = _STORAGE_TYPO.get(int(m.group(2)), int(m.group(2)))
        if ram_v in _MACBOOK_RAM_GB and ssd_v in _MACBOOK_SSD_GB:
            return f"{ram_v}GB", f"{ssd_v}GB"
    return None, None


def _extract_macbook_combo(lower: str) -> tuple[str | None, str | None]:
    """단위 없는 "16/256", "8+256", "14/48/1tb" 표기에서 (RAM, SSD)를 읽는다.

    관용적으로 RAM/SSD 순서로 쓰지만 인치가 앞에 붙는 경우("14/48/1tb")가 있어
    값 화이트리스트로 각 항을 분류한다. 조합에 SSD로 해석되는 항이 없으면
    사양 표기가 아니라고 보고 버린다 — "8/25"(날짜) 류의 오탐을 막는 가드다.
    """
    for m in _MACBOOK_COMBO_RE.finditer(lower):
        parts = [
            (int(num), (unit or "").lower())
            for num, unit in zip(m.groups()[::2], m.groups()[1::2])
            if num is not None
        ]
        ram: str | None = None
        ssd: str | None = None
        for value, unit in parts:
            value = _STORAGE_TYPO.get(value, value)
            if unit in ("tb", "테라"):
                if value in _MACBOOK_SSD_TB and ssd is None:
                    ssd = f"{value}TB"
            elif value in _MACBOOK_SSD_GB:
                if ssd is None:
                    ssd = f"{value}GB"
            elif value in _MACBOOK_RAM_GB and ram is None:
                ram = f"{value}GB"
        if ssd is not None:
            return ram, ssd
    return None, None


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

# 하자 표현은 앞뒤를 봐야 한다 — "무하자", "미파손", "하자 없음", "파손x"는
# 오히려 상태가 좋다는 뜻이다. 실측: 파손 판정 481건 중 234건(49%)이 이런 부정 표현이었다.
# "부품용"·"수리용"은 부정형으로 쓰이지 않아 그대로 둔다.
_DAMAGE_WORDS = r"파손|깨짐|고장|하자|잔상|침수|먹통"
DAMAGE_RE = re.compile(
    rf"부품용|수리용|(?<![무미없])(?:{_DAMAGE_WORDS})(?!\s*(?:없|무|x|X|아님|ㄴㄴ))"
)
SOLD_RE = re.compile(r"거래\s*완료|판매\s*완료|나눔\s*완료")
# 예약중은 아직 팔리지 않은 상태다. sold로 묶으면 시세에서 빠지는데, 예약이 깨지면
# 다시 판매되므로 별도 상태로 둔다 (실측: 당근에만 약 1,000건).
RESERVED_RE = re.compile(r"예약\s*중|예약\s*완료")
# 에르메스 에디션은 일반 모델 대비 가격이 수 배라 SKU 시세를 왜곡한다 (filters.py 가격 상한 주석 참조)
SPECIAL_EDITION_RE = re.compile(r"에르메스|hermes", re.I)


@dataclass
class Extraction:
    target: CrawlTarget
    attributes: dict[str, str] = field(default_factory=dict)  # attr code → 시드 옵션값
    title_matches_target: bool = True
    is_damaged: bool = False
    is_sold: bool = False
    is_reserved: bool = False
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
        if not all(code in self.attributes for code in self.required_codes):
            return False
        # 칩이 지원하지 않는 RAM/SSD/화면 조합(파싱 오류)은 SKU를 만들지 않는다
        return is_valid_config(self.category, self.attributes)


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
        is_reserved=bool(RESERVED_RE.search(title)),
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
        model = chipset = None
        if parsed:
            line, inch, chipset = parsed.groups()
            model = "맥북 에어" if line == "Air" else "맥북 프로"
            attrs["macbook_model"] = model
            attrs["macbook_chipset"] = chipset
            display = _extract_macbook_display(title, line, inch)
            # 칩이 안 나오는 화면(예: base M5에 16인치)이면 타깃의 실제 화면으로 되돌린다
            if not macbook_allows(model, chipset, "macbook_display", display):
                display = f"{inch}인치"
            attrs["macbook_display"] = display
        ram, ssd = _extract_macbook_memory(title)
        # 칩이 지원하지 않는 RAM/SSD는 파싱 오류로 보고 버린다 (틀린 값보다 빈 값)
        if ram and macbook_allows(model, chipset, "macbook_ram", ram):
            attrs["macbook_ram"] = ram
        if ssd and macbook_allows(model, chipset, "macbook_ssd", ssd):
            attrs["macbook_ssd"] = ssd
        color = _extract_color(title, _MACBOOK_COLOR_MATCHER)
        if color:
            attrs["macbook_color"] = color

    elif category == "AppleWatch":
        watch_model = resolve_model_option(target)
        attrs["watch_model"] = watch_model
        mm = _WATCH_MM_RE.search(title)
        if mm:
            attrs["watch_size"] = f"{mm.group(1)}mm"
        elif "울트라" in watch_model or "ultra" in watch_model.lower():
            # 울트라는 전 세대가 49mm 단일 사이즈여서 제목에 mm 표기가 거의 없다
            # (실측: 울트라 매물 1,942건 중 mm 표기 16건). 사이즈를 확정해도 안전하다.
            attrs["watch_size"] = "49mm"
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
