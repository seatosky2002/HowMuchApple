import logging
import re

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.region import EMD, SD, SGG
from app.services.korea_region_codes import SGG_BY_DONG_CODE_PREFIX

logger = logging.getLogger(__name__)

PREFERRED_SD_NAME = "서울특별시"
INVALID_TEXT_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

SD_ALIASES = {
    "서울": "서울특별시",
    "서울시": "서울특별시",
    "부산": "부산광역시",
    "부산시": "부산광역시",
    "대구": "대구광역시",
    "대구시": "대구광역시",
    "인천": "인천광역시",
    "인천시": "인천광역시",
    "광주": "광주광역시",
    "광주시": "광주광역시",
    "대전": "대전광역시",
    "대전시": "대전광역시",
    "울산": "울산광역시",
    "울산시": "울산광역시",
    "세종": "세종특별자치시",
    "세종시": "세종특별자치시",
    "경기": "경기도",
    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "충북": "충청북도",
    "충남": "충청남도",
    "전북": "전북특별자치도",
    "전라북도": "전북특별자치도",
    "전남": "전라남도",
    "경북": "경상북도",
    "경남": "경상남도",
    "제주": "제주특별자치도",
    "제주도": "제주특별자치도",
}


def normalize_sd_name(value: str) -> str:
    return SD_ALIASES.get(value, value)


def region_text_from_dong_code(location_name: str, dong_code: str | None) -> str:
    location_name = clean_region_text(location_name)
    if not location_name:
        return ""
    if dong_code:
        code_region = SGG_BY_DONG_CODE_PREFIX.get(dong_code[:5])
        if code_region:
            sd_name, sgg_name = code_region
            if not sgg_name:
                return f"{sd_name} {location_name}"
            return f"{sd_name} {sgg_name} {location_name}"
    return location_name


def clean_region_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = INVALID_TEXT_RE.sub("", str(value))
    return re.sub(r"\s+", " ", cleaned).strip()


def _tokenize(region_text: str) -> list[str]:
    cleaned = re.sub(r"[,/|·()\[\]]", " ", clean_region_text(region_text))
    cleaned = re.sub(r"\s+", " ", cleaned)
    return [token for token in cleaned.split(" ") if token]


def _extract_sd_name(tokens: list[str]) -> str | None:
    for token in tokens:
        normalized = normalize_sd_name(token)
        if normalized.endswith(("특별시", "광역시", "특별자치시", "특별자치도", "도")):
            return normalized
    return None


def _candidate_sgg_names(tokens: list[str], sd_name: str | None) -> list[str]:
    names = []
    for token in tokens:
        normalized = normalize_sd_name(token)
        if normalized == sd_name:
            continue
        if token.endswith(("시", "군", "구")):
            names.append(token)

    for first, second in zip(tokens, tokens[1:]):
        if normalize_sd_name(first) == sd_name:
            continue
        if first.endswith("시") and second.endswith("구"):
            names.append(f"{first} {second}")

    return list(dict.fromkeys(names))


def _candidate_emd_names(tokens: list[str], sd_name: str | None, sgg_names: list[str]) -> list[str]:
    names = []
    sgg_parts = {part for name in sgg_names for part in name.split()}
    for token in tokens:
        normalized = normalize_sd_name(token)
        if normalized == sd_name or token in sgg_parts:
            continue
        if re.fullmatch(r"\d+", token):
            continue
        if re.search(r"\d", token) and not token.endswith(("동", "읍", "면", "리", "가")):
            continue
        names.append(token)
    return names


def parse_region_parts(region_text: str) -> tuple[str | None, str | None]:
    tokens = _tokenize(region_text)
    if not tokens:
        return None, None

    sd_name = _extract_sd_name(tokens)
    sgg_names = _candidate_sgg_names(tokens, sd_name)
    emd_names = _candidate_emd_names(tokens, sd_name, sgg_names)

    sgg_name = None
    if sgg_names:
        sgg_name = max(sgg_names, key=lambda name: (len(name.split()), len(name)))

    return sgg_name, emd_names[-1] if emd_names else None


async def resolve_emd_id(
    db: AsyncSession,
    region_text: str,
    preferred_sd_name: str = PREFERRED_SD_NAME,
    allowed_sd_names: tuple[str, ...] | None = None,
    preferred_sgg_name: str | None = None,
) -> int | None:
    """Resolve Korean administrative text to an EMD emd_id.

    Supported examples:
      - "서울특별시 강남구 역삼동"
      - "서울 강남구 역삼동"
      - "강남구 역삼동"
      - "역삼동"

    allowed_sd_names가 주어지면 후보를 해당 시도로 제한한다 — 서울·경기만 수집하는
    크롤러(당근)가 동 이름만 있는 주소를 매칭할 때 타 지역 동명이동을 배제하는 용도.
    preferred_sgg_name은 동 이름만 있는 주소의 동명이동 tie-break에 쓴다 (당근은
    지역지정 검색이라 검색에 쓴 앵커의 시군구가 강한 힌트다).
    If a dong-only value matches multiple regions, return None instead of guessing.
    """
    if not region_text:
        return None

    tokens = _tokenize(region_text)
    if not tokens:
        return None

    sd_name = _extract_sd_name(tokens)
    sgg_names = _candidate_sgg_names(tokens, sd_name)
    emd_names = _candidate_emd_names(tokens, sd_name, sgg_names)

    if emd_names:
        candidates = await _find_emd_candidates(db, emd_names, sd_name, sgg_names)
        if allowed_sd_names:
            candidates = [row for row in candidates if row.sd_name in allowed_sd_names]
        candidates = _narrowest_sgg_match(candidates, sgg_names)
        if len(candidates) > 1 and preferred_sgg_name:
            preferred = [row for row in candidates if row.sgg_name == preferred_sgg_name]
            if preferred:
                candidates = preferred
        if len(candidates) > 1 and not sd_name and preferred_sd_name:
            preferred = [row for row in candidates if row.sd_name == preferred_sd_name]
            if preferred:
                candidates = preferred

        if len(candidates) == 1:
            return candidates[0].emd_id
        if len(candidates) > 1:
            labels = [f"{row.sd_name} {row.sgg_name} {row.emd_name}" for row in candidates[:10]]
            logger.warning("지역 매칭 모호: %s -> %s", region_text, labels)
            return None

    if sgg_names:
        return await _fallback_first_emd_in_sgg(db, sgg_names, sd_name or preferred_sd_name)

    return None


def _narrowest_sgg_match(candidates: list, sgg_names: list[str]) -> list:
    """입력에 있던 시군구 표기 중 가장 구체적으로 일치하는 후보만 남긴다.

    "부천시 원미구 중동"은 sgg 후보로 부천시/원미구/부천시 원미구를 모두 만들어내
    구 단위 행이 함께 걸린다. 입력이 구까지 지목했다면 구 단위 행만 정답이다.
    """
    if len(candidates) <= 1 or not sgg_names:
        return candidates
    for name in sorted(sgg_names, key=lambda n: (-len(n.split()), -len(n))):
        exact = [row for row in candidates if row.sgg_name == name]
        if exact:
            return exact
    return candidates


async def _find_emd_candidates(
    db: AsyncSession,
    emd_names: list[str],
    sd_name: str | None,
    sgg_names: list[str],
) -> list:
    query = (
        select(
            EMD.emd_id.label("emd_id"),
            EMD.name.label("emd_name"),
            SGG.name.label("sgg_name"),
            SD.name.label("sd_name"),
        )
        .join(SGG, EMD.sgg_id == SGG.sgg_id)
        .join(SD, SGG.sd_id == SD.sd_id)
        .where(EMD.name.in_(emd_names))
    )
    if sd_name:
        query = query.where(SD.name == sd_name)
    if sgg_names:
        query = query.where(_sgg_name_filter(sgg_names))

    rows = (await db.execute(query.order_by(SD.name, SGG.name, EMD.name))).all()
    return list(rows)


def _sgg_name_filter(sgg_names: list[str]):
    """시군구 이름 조건 — "부천시"가 "부천시 원미구"에도 걸리도록 접두 매칭한다.

    구가 설치된 시(부천·화성·수원 등)의 읍면동은 sgg 행이 "시 구" 형태라서
    구를 생략한 주소("부천시 중동")가 정확히 일치하지 않는다.
    """
    conditions = [SGG.name.in_(sgg_names)]
    conditions += [SGG.name.like(f"{name} %") for name in sgg_names if " " not in name]
    return or_(*conditions)


async def _fallback_first_emd_in_sgg(
    db: AsyncSession,
    sgg_names: list[str],
    sd_name: str | None,
) -> int | None:
    query = (
        select(EMD.emd_id)
        .join(SGG, EMD.sgg_id == SGG.sgg_id)
        .join(SD, SGG.sd_id == SD.sd_id)
        .where(_sgg_name_filter(sgg_names))
        .order_by(EMD.emd_id)
        .limit(1)
    )
    if sd_name:
        query = query.where(SD.name == sd_name)

    return (await db.execute(query)).scalar_one_or_none()
