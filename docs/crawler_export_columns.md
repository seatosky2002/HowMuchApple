# Crawler Export Columns

크롤 결과를 엑셀/CSV로 검증할 때 사용할 컬럼과 용도입니다.

| 컬럼 | 용도 |
|---|---|
| `run_id` | 한 번의 크롤 실행을 묶는 ID입니다. 같은 실행에서 나온 row들은 같은 `run_id`를 가집니다. |
| `crawled_at` | 해당 row를 크롤/저장한 시각입니다. 나중에 언제 수집한 데이터인지 확인합니다. |
| `platform` | 출처 플랫폼입니다. 예: `daangn`, `bunjang`, `joongna`. |
| `crawler_class` | 어떤 크롤러 코드가 만든 row인지 표시합니다. 예: `DaangnCrawler`. |
| `keyword` | 검색에 사용한 키워드입니다. 예: `아이폰`, `맥북`. 키워드별 성능 확인용입니다. |
| `item_rank` | 해당 키워드 결과에서 몇 번째 매물인지입니다. 정렬/상위 노출 확인용입니다. |
| `title` | 매물 제목입니다. 제품/스펙 파싱이 잘 되는지 확인하는 원본 텍스트입니다. |
| `price` | 정수형 가격입니다. 원 단위로 정규화된 값입니다. |
| `url` | 원본 매물 URL입니다. 클릭해서 실제 매물 확인할 때 씁니다. |
| `external_id` | 플랫폼 내부 매물 ID입니다. 중복 저장 방지에 중요합니다. |
| `dedupe_key` | 중복 판별용 키입니다. 보통 `platform + external_id` 조합입니다. |
| `sgg` | 시군구입니다. 예: `강남구`. 지역 파싱/매핑 검증용입니다. |
| `emd` | 읍면동입니다. 예: `역삼동`. 행정동 단위 분석에 필요합니다. |
| `dong_code` | 행정동 10자리 코드입니다. 예: `1120066000`. 플랫폼의 `dongCode` 또는 행정동 코드 자료로 검증합니다. |
| `sku_id` | DB의 SKU ID입니다. 제품 스펙 조합이 어떤 SKU로 연결됐는지 확인합니다. |
| `category_id` | 제품 카테고리 ID입니다. 예: iPhone, iPad, MacBook 등. |
| `status` | 매물 상태입니다. 현재 크롤러는 기본적으로 `active`로 저장합니다. |
| `item_id` | DB에 저장된 `item.item_id`입니다. insert/upsert 이후 확인 가능합니다. |
| `is_new_record` | 새로 insert된 row인지, 기존 row를 update한 건지 표시합니다. |
| `parse_status` | 파싱 결과 상태입니다. 예: `ok`, `parse_error`, `skipped_zero_price`. |
| `parse_error` | 파싱 실패 시 에러 메시지입니다. 성공하면 빈 값입니다. |
| `source_payload_id` | 플랫폼에서 가져온 원본 ID입니다. `external_id` 만들기 전의 raw ID 확인용입니다. |
| `updated_at_db` | DB row의 최종 업데이트 시각입니다. upsert가 실제로 반영됐는지 확인합니다. |

## Grouped Usage

| 목적 | 컬럼 |
|---|---|
| 크롤 실행 추적 | `run_id`, `crawled_at`, `platform`, `crawler_class`, `keyword`, `item_rank` |
| 크롤 원본 검증 | `title`, `price`, `url`, `external_id`, `source_payload_id` |
| 중복 검증 | `external_id`, `dedupe_key`, `platform` |
| 지역 매핑 검증 | `sgg`, `emd`, `dong_code` |
| 상품 매핑 검증 | `sku_id`, `category_id` |
| DB 저장/upsert 검증 | `status`, `item_id`, `is_new_record`, `updated_at_db` |
| 파싱 품질 디버깅 | `parse_status`, `parse_error` |

## Current Code Notes

현재 `CrawledItem`이 실제로 들고 있는 필드는 아래 값입니다.

```text
title
price
url
external_id
source
region_name
dong_code
sku_id
category_id
target_category
target_model
search_keyword
```

따라서 `keyword`, `item_rank`, `parse_status`, `is_new_record`, `updated_at_db` 같은 컬럼은 크롤 검증/엑셀 export 단계에서 추가로 채워야 합니다.
