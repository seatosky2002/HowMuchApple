"""행정구역 마스터(sd/sgg/emd) 시드.

emd 테이블이 비어 있으면 지역 매칭(resolve_emd_id)이 전부 실패하고
프런트 시/도 드롭다운도 빈 목록이 된다. 이 스크립트가 세 테이블을 채운다.

- SD/SGG: `korea_region_codes.SGG_BY_DONG_CODE_PREFIX` (행정표준코드 기준 전국 시군구)
- EMD 소스 ①: 당근 앵커 검증 동 목록 (서울·경기 185개,
  docs/daangn_seoul_gyeonggi_region_codes.md 에서 생성한 상수)
- EMD 소스 ②: item.region_text 중 시도·시군구·읍면동이 온전한 주소(번개/중고나라)를
  파싱해 도출 — 시군구가 공식 목록과 일치할 때만 등록해 오염을 막는다.

idempotent — 이름 기준 get_or_create라 재실행해도 중복이 생기지 않는다.
실행: python -m app.db.seed_regions
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.item import Item
from app.db.models.region import EMD, SD, SGG
from app.db.session import AsyncSessionLocal, engine
from app.services.korea_region_codes import SGG_BY_DONG_CODE_PREFIX
from app.services.region_matcher import _extract_sd_name, _tokenize, parse_region_parts

logger = logging.getLogger(__name__)

# 당근 앵커 순회로 실측 검증된 서울·경기 행정동 (시도, 시군구) -> [동 ...]
DAANGN_VERIFIED_EMDS: dict[tuple[str, str], list[str]] = {
    ("서울특별시", "강남구"): ["논현동", "대치동", "도곡동", "삼성동", "신사동", "압구정동", "역삼1동", "역삼동", "청담동"],
    ("서울특별시", "강동구"): ["강일동", "길동", "둔촌동", "상일동", "성내동", "암사동", "천호동"],
    ("서울특별시", "강북구"): ["미아동", "삼각산동", "삼양동", "수유2동", "수유3동", "수유동"],
    ("서울특별시", "강서구"): ["내발산동", "등촌동", "마곡동", "염창동", "화곡동", "화곡제1동"],
    ("서울특별시", "관악구"): ["낙성대동", "난곡동", "대학동", "봉천동", "신림동", "행운동"],
    ("서울특별시", "광진구"): ["광장동", "구의동", "군자동", "자양동", "중곡동", "화양동"],
    ("서울특별시", "구로구"): ["개봉동", "고척동", "구로동", "구로제1동", "신도림동", "오류동"],
    ("서울특별시", "금천구"): ["가산동", "독산동", "독산제1동", "독산제3동", "시흥동", "시흥제1동"],
    ("서울특별시", "도봉구"): ["도봉동", "방학동", "방학제1동", "쌍문동", "창동", "창제2동"],
    ("서울특별시", "동대문구"): ["답십리동", "용두동", "이문동", "장안동", "전농동", "휘경동"],
    ("서울특별시", "동작구"): ["노량진동", "대방동", "사당동", "상도동", "신대방동", "흑석동"],
    ("서울특별시", "마포구"): ["공덕동", "상암동", "서교동", "성산동", "아현동", "합정동"],
    ("서울특별시", "서대문구"): ["남가좌동", "북가좌동", "연희동", "창천동", "홍은동", "홍제동"],
    ("서울특별시", "서초구"): ["반포동", "방배동", "서초3동", "서초4동", "서초동", "양재동", "잠원동"],
    ("서울특별시", "송파구"): ["문정동", "석촌동", "오금동", "위례동", "잠실동", "잠실본동"],
    ("서울특별시", "양천구"): ["목1동", "목5동", "목동", "신정3동", "신정4동", "신정동"],
    ("서울특별시", "영등포구"): ["대림동", "도림동", "신길동", "여의도동", "여의동", "영등포본동"],
    ("서울특별시", "용산구"): ["이촌동", "이촌제1동", "이태원동", "한강로동", "한남동", "후암동"],
    ("서울특별시", "은평구"): ["녹번동", "대조동", "불광동", "역촌동", "응암동", "진관동"],
    ("서울특별시", "중랑구"): ["망우동", "면목동", "묵동", "상봉동", "신내동", "중화동"],
    ("경기도", "고양시 일산동구"): ["식사동"],
    ("경기도", "고양시 일산서구"): ["대화동", "탄현동"],
    ("경기도", "김포시"): ["고촌읍", "구래동", "장기동", "풍무동"],
    ("경기도", "남양주시"): ["다산동", "별내동", "호평동"],
    ("경기도", "부천시 원미구"): ["도당동", "상3동", "상동", "심곡동", "중1동", "중동"],
    ("경기도", "성남시 분당구"): ["구미동", "백현동", "삼평동", "서현동", "정자동", "판교동"],
    ("경기도", "수원시 권선구"): ["곡반정동", "구운동", "권선1동", "권선동", "금곡동", "호매실동"],
    ("경기도", "수원시 영통구"): ["광교1동", "망포동", "매탄동", "영통동", "원천동", "이의동"],
    ("경기도", "수원시 팔달구"): ["고등동", "매교동", "우만동", "인계동", "화서2동", "화서동"],
    ("경기도", "시흥시"): ["배곧동", "정왕동"],
    ("경기도", "안산시 단원구"): ["고잔동", "초지동"],
    ("경기도", "안산시 상록구"): ["사동"],
    ("경기도", "안양시 동안구"): ["호계동"],
    ("경기도", "용인시 기흥구"): ["구갈동", "동백동", "보정동", "신갈동"],
    ("경기도", "용인시 수지구"): ["죽전동", "풍덕천동"],
    ("경기도", "의정부시"): ["의정부동"],
    ("경기도", "파주시"): ["야당동"],
    ("경기도", "평택시"): ["동삭동", "비전동"],
    ("경기도", "화성시 동탄구"): ["동탄1동", "여울동", "청계동"],
    ("경기도", "화성시 만세구"): ["향남읍"],
}

EMD_SUFFIXES = ("동", "읍", "면", "가", "리")


async def _get_or_create_sd(db: AsyncSession, cache: dict[str, SD], name: str) -> SD:
    if name in cache:
        return cache[name]
    sd = (await db.execute(select(SD).where(SD.name == name))).scalar_one_or_none()
    if sd is None:
        sd = SD(name=name)
        db.add(sd)
        await db.flush()
    cache[name] = sd
    return sd


async def _get_or_create_sgg(db: AsyncSession, cache: dict[tuple[str, str], SGG], sd: SD, name: str) -> SGG:
    key = (sd.name, name)
    if key in cache:
        return cache[key]
    sgg = (
        await db.execute(select(SGG).where(SGG.sd_id == sd.sd_id, SGG.name == name))
    ).scalar_one_or_none()
    if sgg is None:
        sgg = SGG(sd_id=sd.sd_id, name=name)
        db.add(sgg)
        await db.flush()
    cache[key] = sgg
    return sgg


async def _get_or_create_emd(db: AsyncSession, cache: set[tuple[int, str]], sgg: SGG, name: str) -> bool:
    key = (sgg.sgg_id, name)
    if key in cache:
        return False
    emd = (
        await db.execute(select(EMD).where(EMD.sgg_id == sgg.sgg_id, EMD.name == name))
    ).scalar_one_or_none()
    created = emd is None
    if created:
        db.add(EMD(sgg_id=sgg.sgg_id, name=name))
        await db.flush()
    cache.add(key)
    return created


async def seed_regions() -> None:
    sd_cache: dict[str, SD] = {}
    sgg_cache: dict[tuple[str, str], SGG] = {}
    emd_cache: set[tuple[int, str]] = set()
    created_emds = 0

    async with AsyncSessionLocal() as db:
        # 1) 전국 시도/시군구 (행정표준코드 기준)
        for sd_name, sgg_name in SGG_BY_DONG_CODE_PREFIX.values():
            sd = await _get_or_create_sd(db, sd_cache, sd_name)
            await _get_or_create_sgg(db, sgg_cache, sd, sgg_name)

        # 2) 당근 검증 동 목록
        for (sd_name, sgg_name), dongs in DAANGN_VERIFIED_EMDS.items():
            sd = await _get_or_create_sd(db, sd_cache, sd_name)
            sgg = await _get_or_create_sgg(db, sgg_cache, sd, sgg_name)
            for dong in dongs:
                created_emds += await _get_or_create_emd(db, emd_cache, sgg, dong)

        # 3) 수집된 매물 주소에서 도출 (시도+시군구가 온전한 텍스트만)
        region_texts = (
            (await db.execute(select(Item.region_text).where(Item.region_text.is_not(None)).distinct()))
            .scalars()
            .all()
        )
        derived = skipped = 0
        for text in region_texts:
            tokens = _tokenize(text or "")
            sd_name = _extract_sd_name(tokens)
            sgg_name, emd_name = parse_region_parts(text or "")
            if not sd_name or not sgg_name or not emd_name:
                skipped += 1
                continue
            if not emd_name.endswith(EMD_SUFFIXES):
                skipped += 1
                continue
            if (sd_name, sgg_name) not in sgg_cache:
                # 공식 시군구 목록에 없는 조합은 오타/비정상 주소로 보고 버린다
                skipped += 1
                continue
            sgg = sgg_cache[(sd_name, sgg_name)]
            if await _get_or_create_emd(db, emd_cache, sgg, emd_name):
                created_emds += 1
                derived += 1

        await db.commit()

        sd_count = len(sd_cache)
        sgg_count = len(sgg_cache)
        emd_count = len(emd_cache)

    await engine.dispose()
    print(
        f"시드 완료 — 시도 {sd_count} / 시군구 {sgg_count} / 읍면동 {emd_count}"
        f" (이번에 생성된 읍면동 {created_emds}, 매물 주소 도출 {derived}, 스킵 {skipped})"
    )


if __name__ == "__main__":
    asyncio.run(seed_regions())
