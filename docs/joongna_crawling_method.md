# 중고나라 크롤링 방법

> 2026-07-17 작성. 서울·경기 매물 최대 수집을 위해 중고나라의 지역 검색 지원 여부를 조사하고,
> 전국 전량 수집 + 지역 라벨 필터 방식을 설계·실행한 기록.

## 한 줄 요약

중고나라는 당근처럼 "지역을 지정해서" 검색할 수 없다. 대신 검색 API가 **전체 결과를 페이지네이션으로 끝까지 내어주고, 매물마다 판매자 지역(`locationNames`)이 붙어 나오므로**, 전국을 통째로 수집한 뒤 지역 라벨로 서울/경기를 골라내는 방식을 쓴다.

## 왜 이 방식인가 (조사 결과)

당근은 `?in=<동이름-코드>`로 동네를 지정해야만 그 지역 매물이 나오는 구조라 동 코드 185개를 순회한다 (→ `daangn_seoul_gyeonggi_region_codes.md`). 중고나라는 구조가 다르다:

| 시도 | 결과 |
|---|---|
| URL 지역 파라미터 | 없음. 웹 프론트(데스크톱/모바일)에 지역 필터 UI 자체가 없음 (앱 전용 기능) |
| 검색 API의 `locationFilter` 필드 | 필드는 존재하나(400 타입에러로 확인) 스키마가 앱 전용. 객체/문자열/좌표/행정코드 등 10여 가지 형식을 넣어봤지만 전부 500 → 사용 불가 |
| 검색어에 동 이름 포함 (`"천호동 아이폰 14 프로"`) | ✅ 동작함. 제목에 동 이름이 없어도 매물의 구조화된 지역 필드와 매칭됨 (천호제1동·천호제3동 매물만 반환) |
| 전국 검색 + `locationNames` 후처리 | ✅ **채택.** 동 키워드 검색의 상위집합임을 검증 (천호동 3건이 전국 1,151건에 전부 포함). 요청 수는 동별 순회의 약 1/7 |

동별 검색은 결국 전국 검색의 부분집합이므로, 전국 전량 수집이 누락 없이 더 적은 요청으로 같은 목적을 달성한다.

## 검색 API 스펙

```
POST https://search-api.joongna.com/v3/search/all
Content-Type: application/json
Origin: https://web.joongna.com
```

요청 body (웹 프론트가 실제로 보내는 형식을 그대로 사용):

```json
{
  "osType": 2,
  "firstQuantity": 50, "quantity": 50,
  "jnPayYn": "ALL",
  "categoryFilter": [{"categoryDepth": 0, "categorySeq": 0}],
  "priceFilter": {"minPrice": 0, "maxPrice": 100000000},
  "sort": "RECENT_SORT",
  "saleYn": "SALE_N", "parcelFeeYn": "ALL",
  "page": 0,
  "searchWord": "아이폰 14 프로",
  "adjustSearchKeyword": true,
  "keywordSource": "INPUT_KEYWORD",
  "registPeriod": "ALL"
}
```

응답의 `data.items[]`에서 사용하는 필드:

| 필드 | 용도 |
|---|---|
| `seq` | 상품 고유번호. 중복 제거 키, 상품 URL(`https://web.joongna.com/product/{seq}`) |
| `title`, `price` | 제목/가격. 별도 파싱 불필요 |
| `locationNames` | 판매자 지역, 예: `["서울특별시 강동구 천호제3동"]`. 택배 전용 판매자는 빈 배열 |
| `objectType` | `"product"`만 수집 (광고·게시글 제외) |

## 수집 파이프라인

1. **검색 단위 = 모델 키워드.** 타겟 72개 모델의 별칭 포함 총 227개 키워드 (예: iPhone SE 3세대 → `아이폰 SE 3세대`, `아이폰SE3`, `iPhone SE 3`, `iPhone SE 2022`). 동시에 4개 키워드씩 병렬 진행.
2. **키워드당 페이지 전량 순회.** `page`를 0부터 올리며 50개씩 요청. 신규 매물이 2페이지 연속 안 나오면 종료 (안전장치: 최대 40페이지). 페이지 간 0.3초 대기, 429/5xx 응답 시 10초+ 백오프 후 재시도 (최대 3회).
3. **필터링.** `objectType == "product"`, 가격 > 0, 그리고 기존 `matches_target_listing()`으로 제목·가격이 타겟 모델과 실제로 맞는지 검증 — "아이폰 14 프로 케이스" 같은 액세서리 제거.
4. **중복 제거.** `seq` 기준 전역 dedup. 같은 매물이 여러 키워드에 걸려도 1건 (먼저 매칭된 타겟 소속).
5. **지역 라벨링.** `locationNames[0]`을 그대로 저장, 시도(서울/경기/...)별 분류는 후처리. 상세페이지 조회 불필요 — 기존 크롤러(`app/crawlers/joongna.py`)가 매물마다 상세페이지를 열어 지역을 뽑던 과정이 통째로 사라진다.

### 페이지네이션 전량 수집 검증

"아이폰 14 프로" 단일 키워드로 사전 검증: 전체 1,151건 중 1,124건(97.7%)이 25페이지 만에 수집됨. 누락분은 크롤 도중 올라온 신규 매물과 정렬 흔들림 수준. 즉 이 API는 검색 결과를 잘라내지 않는다.

## 실행 결과 (2026-07-17)

- 총 요청 약 2,500회 (키워드당 평균 ~11페이지), 소요 약 12분, 차단 없음
- **고유 매물 6,288건** → `backend/exports/joongna_all_regions_crawl.csv`
  (컬럼: `external_id, category, model, title, price, region, search_keyword, url`)

| 지역 | 매물 수 |
|---|---|
| 서울특별시 | 1,392 |
| 경기도 | 1,308 |
| **서울/경기 소계** | **2,700** |
| 지역 미표기 (택배거래 판매자) | 1,693 |
| 그 외 지방 | 1,895 |

모델 상위: AirPods Pro 2 (605), AirPods Pro 3 (509), iPhone 15 (331), Watch SE 2 (318), iPhone 14 (285), …

기존 Playwright 방식(모델당 30개 상한, 스크롤 + 상세페이지 조회) 대비: 상한 없이 전량 수집, 브라우저 불필요, 매물당 상세 요청 제거.

## 크롤러 본체 교체 (2026-07-17)

위 방식을 검증한 뒤 `app/crawlers/joongna.py`를 전면 재작성했다. 클래스명(`JoognaCrawler`)과
반환 형식(`CrawledItem`)은 그대로라 `run.py`/`base.py` 등 호출부 변경은 없다.

| | 기존 (Playwright 방식) | 교체 후 (API 방식) |
|---|---|---|
| 수집 경로 | 브라우저로 검색 페이지 열어 무한스크롤 + HTML 정규식 파싱 (+ httpx HTML 폴백) | `search-api` POST 호출, JSON 응답 파싱 |
| 지역 정보 | 매물마다 **상세페이지를 별도 요청**해 `locationName`/`dongCode` 추출 | 검색 응답의 `locationNames`를 바로 사용 (매물당 추가 요청 0회) |
| 수집량 | 타겟(모델)당 30개 상한 (`default_items_per_target`) | 상한 없음 — 키워드별 전 페이지 순회, `max_items` 지정 시에만 제한 |
| 키워드 | 타겟당 키워드 순회하되 30개 차면 중단 | 별칭 포함 전 키워드 순회 + `seq` 기준 중복 제거 |
| 의존성 | playwright(chromium) + httpx | httpx만 |
| dong_code | 상세페이지에서 채움 | **채우지 않음** (`None`) — DB의 지역 매칭(`emd_id`)은 `region_name` 텍스트 파싱으로 동작하므로 영향 없음. 행정동 코드가 꼭 필요하면 상세페이지 조회를 별도 후처리로 |
| 정확도 필터 | `matches_target_listing()` | 동일하게 유지 + `objectType == "product"`(광고·게시글 제외) 추가 |
| 요청 제어 | 스크롤 대기 위주 | 동시 4타겟, 페이지 간 0.3초, 429/5xx 백오프 재시도 |

검증: 타겟 2개(iPhone 14 Pro, iPhone 15) 제한 실행으로 매물 수집·지역 라벨·중복 제거·`max_items` 상한 동작 확인.

## 참고: 매물 상세의 지역 정보

상세 페이지(`web.joongna.com/product/{seq}`) HTML에는 `locationName`, `dongCode`(행정동 코드)가 들어 있으며 기존 `app/crawlers/joongna.py`의 `_fetch_detail_regions()`가 이를 사용한다. 검색 API가 `locationNames`를 바로 주므로 대량 수집에는 불필요하지만, 행정동 코드가 필요한 경우엔 이 경로를 쓴다.

## 관련 자료

- 수집 스크립트: `backend/scripts/crawl_joongna_all.py` (위 파이프라인 구현, 수동 실행/DB 미사용)
- 당근 동별 수집 스크립트: `backend/scripts/crawl_daangn_all_dongs.py`
- 당근 방식(동 코드 순회): `docs/daangn_seoul_gyeonggi_region_codes.md`
