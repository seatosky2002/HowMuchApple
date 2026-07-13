import re

from app.crawlers.targets import CrawlTarget


# 카테고리별 (최저가, 최고가). 코퍼스 분석 기반: 하한은 공박스/케이블/placeholder 가격을,
# 상한은 999,999,999원류 placeholder를 거른다. 최고 사양 CTO 신품은 통과하도록 여유를 둔다.
PRICE_BOUNDS: dict[str, tuple[int, int]] = {
    "iPhone": (50_000, 3_500_000),
    "iPad": (50_000, 4_000_000),
    "MacBook": (100_000, 12_000_000),
    "AppleWatch": (30_000, 2_000_000),  # 에르메스 등 특수 에디션은 SKU 시세를 왜곡하므로 제외
    "AirPods": (20_000, 1_000_000),
}
DEFAULT_PRICE_BOUNDS = (10_000, 20_000_000)

ACCESSORY_TERMS = (
    "케이스티파이",
    "casetify",
    "케이스",
    "필름",
    "강화유리",
    "보호유리",
    "렌즈필터",
    "렌즈보호",
    "사생활보호",
    "스트랩",
    "시계줄",
    "워치줄",
    "밴드",
    "그립톡",
    "카드지갑",
    "파우치",
    "거치대",
    "범퍼",
    "스킨",
    "스티커",
    "키링",
    "충전기",
    "어댑터",
    "케이지",
    "스몰리그",
    "smallrig",
    "촬영리그",
    "유선이어폰",
    "이어팟",
    "earpods",
    "박스만",
    "공박스",
    "빈박스",
    "구성품만",
    "케이블만",
    "충전케이블",
    "충전선",
    "부품용",
    "이어팁",
)

# 케이스 브랜드 — 제목에 '케이스'를 안 쓰는 케이스 매물을 거른다.
# 주의: '펜슬'/'매직키보드'는 정상 기기+악세사리 번들 제목에 흔해서(코퍼스 133건 중 저가 0건) 넣지 않는다.
CASE_BRAND_TERMS = (
    "어반소피스티케이션",
    "슈피겐",
    "spigen",
    "오터박스",
    "otterbox",
    "신지모루",
    "베루스",
    "링케",
    "ringke",
    "파인우븐",
)

# 업자 광고/렌탈 — 개인 중고 시세가 아닌 글.
# 주의: '할부'/'특가'/'파손'은 정상 매물 제목에도 쓰여서 넣지 않는다.
BIZ_AD_TERMS = (
    "렌탈",
    "대여",
    "단기임대",
    "통신사용",
    "기기변경",
    "번호이동",
    "당일개통",
    "즉시개통",
    "성지",
    "좌표",
    "페이백",
    "현금완납",
    "요금제",
)

IPHONE_ACCESSORY_TERMS = (
    "맥세이프배터리",
    "맥세이프충전",
    "맥세이프케이스",
    "맥세이프지갑",
    "맥세이프카드지갑",
    "정품맥세이프",
    "맥세이프정품",
    "맥세이프정품배터리",
    "맥세이프미개봉",
)

WANTED_TERMS = (
    "구매합니다",
    "구매해요",
    "구매원합니다",
    "구매해봅니다",
    "구매희망",
    "구입합니다",
    "구입해요",
    "구입원합니다",
    "구해요",
    "구합니다",
    "삽니다",
    "사요",
    "매입",
    "교환",
    "교환원합니다",
    "교환원해요",
    "교환원함",
    "교환합니다",
    "교환희망",
    "교환가능",
    "교환하실분",
)

AIRPODS_PART_TERMS = (
    "유닛",
    "한쪽",
    "한짝",
    "낱개",
    "왼쪽",
    "오른쪽",
    "좌측",
    "우측",
    "본체만",
    "본체",
    "본통",
    "충전본체",
    "충전케이스",
)


def matches_target_listing(title: str, price: int, target: CrawlTarget) -> bool:
    """제목 + 가격을 함께 검증하는 크롤러용 단일 게이트."""
    return within_price_bounds(price, target) and matches_target_title(title, target)


def within_price_bounds(price: int, target: CrawlTarget) -> bool:
    low, high = PRICE_BOUNDS.get(target.category, DEFAULT_PRICE_BOUNDS)
    return low <= price <= high


def matches_target_title(title: str, target: CrawlTarget) -> bool:
    compact = _compact(title)
    if not compact:
        return False
    if (
        _has_any(compact, ACCESSORY_TERMS)
        or _has_any(compact, WANTED_TERMS)
        or _has_any(compact, CASE_BRAND_TERMS)
        or _has_any(compact, BIZ_AD_TERMS)
    ):
        return False

    if target.category == "iPhone":
        return _matches_iphone(compact, target.model)
    if target.category == "iPad":
        return _matches_ipad(compact, target.model)
    if target.category == "MacBook":
        return _matches_macbook(compact, target.model)
    if target.category == "AppleWatch":
        return _matches_watch(compact, target.model)
    if target.category == "AirPods":
        return _matches_airpods(compact, target.model)

    return any(_compact(keyword) in compact for keyword in target.keywords)


def _matches_iphone(compact: str, model: str) -> bool:
    if not _has_any(compact, ("아이폰", "iphone")):
        return False
    if _has_any(compact, IPHONE_ACCESSORY_TERMS):
        return False
    if "SE 3rd" in model:
        return _has_any(compact, ("아이폰se3", "iphonese3", "se3세대", "se2022"))
    if "Air" in model:
        return _has_any(compact, ("아이폰에어", "iphoneair"))
    if model.endswith("16e"):
        return _has_any(compact, ("아이폰16e", "iphone16e"))
    if model.endswith("17e"):
        return _has_any(compact, ("아이폰17e", "iphone17e"))

    number_match = re.search(r"iPhone (\d+)", model)
    if not number_match:
        return False
    number = number_match.group(1)
    if not _matches_iphone_number(compact, number):
        return False
    if _has_any(compact, (f"아이폰{number}e", f"iphone{number}e")) and not model.endswith(f"{number}e"):
        return False

    plus = _has_any(compact, ("플러스", "plus"))
    pro_max = _has_any(compact, ("프로맥스", "프로max", "promax"))
    pro = _has_any(compact, ("프로", "pro"))
    max_only = _has_any(compact, ("맥스", "max"))

    if "Pro Max" in model:
        return pro_max
    if "Pro" in model:
        return pro and not pro_max and not plus and not max_only
    if "Plus" in model:
        return plus and not pro and not pro_max
    return not plus and not pro and not pro_max and not max_only


def _matches_iphone_number(compact: str, number: str) -> bool:
    # "아이폰16s 16GB"(구형 6s/Xs류 오기입)는 제외하되 "아이폰16 S급"(상태 등급)은 허용한다.
    return re.search(rf"(?:아이폰|iphone){number}(?!s(?!급))", compact) is not None


def _matches_ipad(compact: str, model: str) -> bool:
    if not _has_any(compact, ("아이패드", "ipad")):
        return False

    is_air = _has_any(compact, ("에어", "air"))
    is_pro = _has_any(compact, ("프로", "pro"))
    is_mini = _has_any(compact, ("미니", "mini"))

    if "mini" in model:
        return is_mini and _has_any(compact, ("a17", "7세대", "mini7", "미니7"))
    if "Air" in model:
        if not is_air or is_pro:
            return False
        if "5th" in model:
            return _has_any(compact, ("5세대", "m1"))
        return _requires_chip_and_optional_size(compact, model)
    if "Pro" in model:
        if not is_pro:
            return False
        if "4th" in model:
            return _has_any(compact, ("11",)) and _has_any(compact, ("4세대", "m2"))
        if "6th" in model:
            return _has_any(compact, ("12.9", "129")) and _has_any(compact, ("6세대", "m2"))
        return _requires_chip_and_optional_size(compact, model)
    if "A16" in model:
        return not is_air and not is_pro and not is_mini and _has_any(compact, ("a16", "11세대", "11th"))
    if "10th" in model:
        return not is_air and not is_pro and not is_mini and _has_any(compact, ("10세대", "10th"))
    return False


def _matches_macbook(compact: str, model: str) -> bool:
    if not _has_any(compact, ("맥북", "macbook")):
        return False

    is_air = _has_any(compact, ("에어", "air"))
    is_pro = _has_any(compact, ("프로", "pro"))
    if "Air" in model and (not is_air or is_pro):
        return False
    if "Pro" in model and not is_pro:
        return False

    chip_match = re.search(r"\bM([2-5])(?: (Pro|Max))?\b", model)
    if not chip_match:
        return False
    chip = f"m{chip_match.group(1)}"
    tier = chip_match.group(2)
    if tier:
        return _has_any(compact, (f"{chip}{tier.lower()}", f"{chip}{_korean_chip_tier(tier)}"))
    return _has_any(compact, (chip,)) and not _has_any(compact, (f"{chip}pro", f"{chip}max"))


def _matches_watch(compact: str, model: str) -> bool:
    if not _has_any(compact, ("애플워치", "applewatch")):
        return False
    ultra = _has_any(compact, ("울트라", "ultra"))
    se = bool(re.search(r"(애플워치|applewatch|watch)se(?:\d|세대|$)", compact))

    if "Ultra 3" in model:
        return ultra and _has_any(compact, ("3",))
    if "Ultra 2" in model:
        return ultra and _has_any(compact, ("2",))
    if model.endswith("Ultra"):
        return ultra and not _has_any(compact, ("2", "3"))
    if "SE 3rd" in model:
        return se and _has_any(compact, ("3", "3세대"))
    if "SE 2nd" in model:
        return se and _has_any(compact, ("2", "2세대"))

    series_match = re.search(r"Series (\d+)", model)
    return bool(series_match and not ultra and not se and series_match.group(1) in compact)


def _matches_airpods(compact: str, model: str) -> bool:
    if not _has_any(compact, ("에어팟", "airpods", "airpod")):
        return False
    if _has_any(compact, AIRPODS_PART_TERMS):
        return False

    pro = _has_any(compact, ("프로", "pro"))
    max_model = _has_any(compact, ("맥스", "max"))
    type_c = _has_any(compact, ("c타입", "usbc", "usb-c", "typec"))
    anc = _has_any(compact, ("노이즈캔슬링", "노캔", "anc"))

    if "Max" in model:
        return max_model and type_c
    if "Pro 3rd" in model:
        return pro and _has_any(compact, ("3세대", "프로3", "pro3"))
    if "USB-C" in model:
        return pro and _has_any(compact, ("2세대", "프로2", "pro2")) and type_c
    if "Pro 2nd" in model:
        return pro and _has_any(compact, ("2세대", "프로2", "pro2")) and not type_c
    if "ANC" in model:
        return _has_any(compact, ("4세대", "에어팟4", "airpods4", "airpod4")) and anc
    if model.endswith("AirPods 4"):
        return _has_any(compact, ("4세대", "에어팟4", "airpods4", "airpod4")) and not anc
    return False


def _requires_chip_and_optional_size(compact: str, model: str) -> bool:
    chip_match = re.search(r"\bM([1-5])\b", model)
    if chip_match and f"m{chip_match.group(1)}" not in compact:
        return False

    size_match = re.search(r"(\d+(?:\.\d+)?)-inch", model)
    if not size_match:
        return True
    size = size_match.group(1)
    return size.replace(".", "") in compact or size in compact


def _korean_chip_tier(tier: str) -> str:
    return {"Pro": "프로", "Max": "맥스"}[tier]


def _has_any(compact: str, terms: tuple[str, ...]) -> bool:
    return any(_compact(term) in compact for term in terms)


def _compact(value: str) -> str:
    normalized = value.lower().replace("+", "plus")
    return re.sub(r"[\W_]+", "", normalized)
