# HowMuch API — Endpoint 설계서

> 상태: 설계 중 (미구현)
> Base URL: `/api/v1`
> 인증 방식: JWT — **HttpOnly 쿠키** (access_token, refresh_token)
> CSRF 대응: SameSite=Strict 설정으로 커버

---

## 토큰 전략

| 토큰 | 저장 위치 | 만료 | 비고 |
|------|----------|------|------|
| access_token | HttpOnly Cookie | 30분 | 매 요청 자동 전송 |
| refresh_token | HttpOnly Cookie + DB | 14일 | Rotation — 사용 시 새 토큰 발급 & 이전 revoke |

**Rotation 보안 규칙**: revoke된 refresh_token이 재사용되면 해당 유저의 모든 세션 강제 종료.

**로그아웃**: refresh_token DB revoke + 두 쿠키 즉시 만료 Set-Cookie.

---

## 1. 인증 (Auth)

> 보안: 모든 응답에서 토큰은 Response Body가 아닌 **Set-Cookie 헤더**로만 전달.

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| POST | `/auth/register` | 회원가입 | ✗ |
| POST | `/auth/login` | 로그인 (쿠키 발급) | ✗ |
| POST | `/auth/logout` | 로그아웃 (쿠키 삭제 + DB revoke) | ✓ |
| POST | `/auth/refresh` | access_token 재발급 (refresh 쿠키 사용) | ✗ (쿠키) |
| POST | `/auth/password-reset/request` | 비밀번호 재설정 이메일 발송 | ✗ |
| POST | `/auth/password-reset/confirm` | 인증 코드 검증 후 비밀번호 변경 | ✗ |
| GET | `/auth/oauth/{provider}/redirect` | 소셜 로그인 시작 — provider: `kakao`, `apple` | ✗ |
| GET | `/auth/oauth/{provider}/callback` | 소셜 로그인 콜백 (쿠키 발급) | ✗ |
| POST | `/auth/account/restore` | 탈퇴 취소 (30일 이내, 재로그인 시 호출) | ✓ |

### POST `/auth/register`
> 가입 후 이메일 인증 완료 전까지는 `is_verified=false`. 인증 완료 시 알림 수신 가능.

```json
// Request
{
  "email": "user@example.com",
  "password": "...",
  "nickname": "변민규"
}

// Response 201
{
  "user_id": 1,
  "email": "user@example.com",
  "nickname": "변민규",
  "is_verified": false
}
// + Set-Cookie: access_token=...; HttpOnly; SameSite=Strict; Path=/
// + Set-Cookie: refresh_token=...; HttpOnly; SameSite=Strict; Path=/api/v1/auth/refresh
```

### POST `/auth/login`
```json
// Request
{ "email": "user@example.com", "password": "..." }

// Response 200
{ "user_id": 1, "nickname": "변민규" }
// + Set-Cookie: access_token=...
// + Set-Cookie: refresh_token=...
```

### POST `/auth/logout`
```json
// Response 200 (쿠키 만료 + DB revoke)
{ "message": "logged out" }
// + Set-Cookie: access_token=; Max-Age=0
// + Set-Cookie: refresh_token=; Max-Age=0
```

### POST `/auth/refresh`
> refresh_token 쿠키로 자동 인증. Rotation 적용.

```json
// Response 200
{ "ok": true }
// + Set-Cookie: access_token=... (새 토큰)
// + Set-Cookie: refresh_token=... (새 토큰, 이전 토큰 revoke)
```

### POST `/auth/password-reset/request`
```json
// Request
{ "email": "user@example.com" }

// Response 200 (이메일 존재 여부 노출 금지)
{ "message": "이메일이 존재하면 인증 메일을 발송했습니다." }
```

### POST `/auth/password-reset/confirm`
```json
// Request
{ "token": "reset-token-from-email", "new_password": "..." }

// Response 200
{ "message": "비밀번호가 변경되었습니다." }
```

### GET `/auth/oauth/{provider}/redirect`
> 브라우저를 소셜 로그인 페이지로 리다이렉트. provider: `kakao` | `apple`

```
// Response 302 → 소셜 로그인 페이지
```

### GET `/auth/oauth/{provider}/callback`
> 소셜 인증 완료 후 리다이렉트되는 콜백. 최초 로그인 시 자동 회원가입.

```json
// Response 200
{ "user_id": 1, "nickname": "변민규", "is_new": true }
// + Set-Cookie: access_token=...
// + Set-Cookie: refresh_token=...
```

### POST `/auth/account/restore`
> 탈퇴 후 30일 이내 재로그인 시 복구 요청. 로그인 직후 호출.

```json
// Response 200
{ "message": "계정이 복구되었습니다." }
```

---

## 2. 사용자 (Users)

> 보안: URL에 user_id 노출 없이 토큰으로 본인 식별 (`/me` 패턴).

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/users/me` | 내 프로필 조회 | ✓ |
| PATCH | `/users/me` | 내 정보 수정 (닉네임 등) | ✓ |
| PATCH | `/users/me/password` | 현재 로그인 상태에서 비밀번호 변경 | ✓ |
| DELETE | `/users/me` | 회원 탈퇴 (Soft Delete) | ✓ |
| POST | `/users/check-email` | 이메일 중복 확인 | ✗ |
| POST | `/users/check-nickname` | 닉네임 중복 확인 | ✗ |
| GET | `/users/me/notification-settings` | 알림 설정 조회 | ✓ |
| PATCH | `/users/me/notification-settings` | 알림 설정 수정 | ✓ |

### GET `/users/me`
```json
// Response 200
{
  "user_id": 1,
  "email": "user@example.com",
  "nickname": "변민규",
  "is_verified": true,
  "alert_channels": {
    "email": true,
    "sms": false
  },
  "phone": "010-****-5678",
  "created_at": "2026-05-31T12:00:00+09:00"
}
```

### PATCH `/users/me`
```json
// Request (변경할 필드만)
{ "nickname": "새닉네임" }
```

### PATCH `/users/me/password`
> 현재 비밀번호 확인 후 변경. forgot-password 플로우와 별개.

```json
// Request
{
  "current_password": "...",
  "new_password": "..."
}
// Response 200
{ "message": "비밀번호가 변경되었습니다." }
```

### DELETE `/users/me`
> Soft Delete — `deleted_at` 타임스탬프 기록. 즉시 로그인 불가, 30일 후 완전 삭제.

```json
// Response 200
{ "message": "탈퇴 처리되었습니다. 30일 이내 재로그인 시 복구 가능합니다." }
```

### POST `/users/check-email`
```json
// Request
{ "email": "user@example.com" }
// Response 200
{ "available": true }
```

### POST `/users/check-nickname`
```json
// Request
{ "nickname": "변민규" }
// Response 200
{ "available": false }
```

### GET `/users/me/notification-settings`
```json
// Response 200
{
  "channels": {
    "email": true,
    "sms": false
  },
  "dnd": {
    "enabled": true,
    "start": "23:00",
    "end": "08:00"
  },
  "watchlist_alerts_enabled": true
}
```

### PATCH `/users/me/notification-settings`
```json
// Request (변경할 필드만)
{
  "channels": { "sms": true },
  "dnd": { "enabled": true, "start": "22:00", "end": "07:00" }
}
```

---

## 3. 인증/검증 (Verifications)

> **Rate Limiting 필수**: DDoS·비용 폭탄 방지. IP당 분당 3회, 일 10회 제한.
> 이메일·전화번호 인증 완료 시 알림 채널로 사용 가능.

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| POST | `/verifications/email` | 이메일 인증번호 발송 | ✓ |
| POST | `/verifications/email/verify` | 이메일 인증번호 확인 | ✓ |
| POST | `/verifications/phone` | 휴대폰 인증번호 발송 (SMS) | ✓ |
| POST | `/verifications/phone/verify` | 휴대폰 인증번호 확인 | ✓ |

### POST `/verifications/email`
```json
// Request
{ "email": "user@example.com" }
// Response 200
{ "message": "인증번호를 발송했습니다. 5분 내 입력해주세요." }
```

### POST `/verifications/email/verify`
```json
// Request
{ "email": "user@example.com", "code": "123456" }
// Response 200
{ "verified": true }
```

### POST `/verifications/phone`
```json
// Request
{ "phone": "010-1234-5678" }
// Response 200
{ "message": "인증번호를 발송했습니다." }
```

### POST `/verifications/phone/verify`
```json
// Request
{ "phone": "010-1234-5678", "code": "123456" }
// Response 200
{ "verified": true }
```

---

## 4. 카탈로그 (Categories)

> 기존 `/products` 그룹을 대체. ERD의 CATEGORY_ATTRIBUTE 구조를 그대로 노출해
> 프론트엔드가 동적 폼을 렌더링할 수 있도록 속성 메타데이터 포함.

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/categories` | 전체 카테고리 목록 | ✗ |
| GET | `/categories/{category_id}/attributes` | 카테고리별 속성 정의 (폼 렌더링용) | ✗ |

### GET `/categories`
```json
// Response 200
{
  "categories": [
    { "category_id": 1, "name": "iPhone" },
    { "category_id": 2, "name": "iPad" },
    { "category_id": 3, "name": "MacBook" },
    { "category_id": 4, "name": "AppleWatch" },
    { "category_id": 5, "name": "AirPods" }
  ]
}
```

### GET `/categories/{category_id}/attributes`
> `is_required`, `display_group`, `sort_order`, 선택 가능한 `options` 포함.
> 프론트엔드는 이 응답으로 스펙 입력 폼을 동적 생성.

```json
// GET /categories/1/attributes  (iPhone)
// Response 200
{
  "category_id": 1,
  "name": "iPhone",
  "attributes": [
    {
      "attribute_id": 1,
      "code": "model",
      "label": "모델",
      "datatype": "option",
      "is_required": true,
      "display_group": "기본 정보",
      "sort_order": 1,
      "options": [
        { "option_id": 1, "value": "iPhone 16 Pro", "sort_order": 1 },
        { "option_id": 2, "value": "iPhone 16", "sort_order": 2 },
        { "option_id": 3, "value": "iPhone 15 Pro", "sort_order": 3 }
      ]
    },
    {
      "attribute_id": 2,
      "code": "storage",
      "label": "용량",
      "datatype": "option",
      "is_required": true,
      "display_group": "기본 정보",
      "sort_order": 2,
      "options": [
        { "option_id": 10, "value": "128GB", "sort_order": 1 },
        { "option_id": 11, "value": "256GB", "sort_order": 2 },
        { "option_id": 12, "value": "512GB", "sort_order": 3 }
      ]
    },
    {
      "attribute_id": 3,
      "code": "color",
      "label": "색상",
      "datatype": "option",
      "is_required": false,
      "display_group": "기본 정보",
      "sort_order": 3,
      "options": [
        { "option_id": 20, "value": "자연색 티타늄", "sort_order": 1 }
      ]
    }
  ]
}
```

---

## 5. 지역 (Regions)

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/regions` | 시도(sd) 목록 | ✗ |
| GET | `/regions/{sd_id}/sgg` | 시군구 목록 | ✗ |
| GET | `/regions/{sgg_id}/emd` | 읍면동 목록 | ✗ |

```json
// GET /regions
{ "regions": [{ "sd_id": 1, "name": "서울특별시" }, ...] }

// GET /regions/1/sgg
{ "sgg": [{ "sgg_id": 1, "name": "강남구" }, ...] }

// GET /regions/1/emd
{ "emd": [{ "region_id": 1, "name": "역삼동" }, ...] }
```

---

## 6. SKU

> ERD에서 WATCHLIST.sku_id가 FK이므로, 찜 등록 전 반드시 SKU를 resolve해야 함.
> 스펙 조합 → sku_id 흐름: `/categories/{id}/attributes` → 스펙 선택 → `/sku/resolve` → sku_id 획득 → `/watchlist` POST

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| POST | `/sku/resolve` | 스펙 조합 → sku_id 반환. 없으면 생성. | ✗ |
| GET | `/sku/{sku_id}` | SKU 정보 + 현재 시세 요약 | ✗ |
| GET | `/sku/{sku_id}/price-trend` | 가격 추이 (차트용) | ✗ |
| GET | `/sku/{sku_id}/region-prices` | 지역별 평균가 목록 (히트맵용) | ✗ |

### POST `/sku/resolve`
```json
// Request
{
  "category_id": 1,
  "attributes": [
    { "attribute_id": 1, "option_id": 3 },
    { "attribute_id": 2, "option_id": 11 },
    { "attribute_id": 3, "option_id": 20 }
  ]
}

// Response 200
{
  "sku_id": 42,
  "category": "iPhone",
  "label": "iPhone 15 Pro 256GB 자연색 티타늄",
  "fingerprint": "iphone-15pro-256gb-natural"
}
```

### GET `/sku/{sku_id}`
```json
// Response 200
{
  "sku_id": 42,
  "category": "iPhone",
  "label": "iPhone 15 Pro 256GB 자연색 티타늄",
  "attributes": [
    { "code": "model", "label": "모델", "value": "iPhone 15 Pro" },
    { "code": "storage", "label": "용량", "value": "256GB" },
    { "code": "color", "label": "색상", "value": "자연색 티타늄" }
  ],
  "price_summary": {
    "avg_price": 1050000,
    "min_price": 850000,
    "max_price": 1300000,
    "listing_count": 42,
    "updated_at": "2026-05-31T00:00:00+09:00"
  }
}
```

### GET `/sku/{sku_id}/price-trend`
```
Query params:
  region_id=42    (생략 시 서울 전체)
  period=4w       (4w | 8w | 3m | 6m | 1y)
```

```json
// Response 200
{
  "sku_id": 42,
  "region": "서울특별시 강남구 역삼동",
  "period": "4w",
  "change_rate": -2.5,
  "chart_data": [
    { "bucket_ts": "2026-05-03", "avg_price": 1100000, "listing_count": 10 },
    { "bucket_ts": "2026-05-10", "avg_price": 1080000, "listing_count": 12 },
    { "bucket_ts": "2026-05-17", "avg_price": 1060000, "listing_count": 9 },
    { "bucket_ts": "2026-05-24", "avg_price": 1050000, "listing_count": 11 }
  ]
}
```

### GET `/sku/{sku_id}/region-prices`
```
Query params:
  sd_id=1     (시도 단위, 생략 시 전국)
  level=sgg   (sgg | emd, 기본 sgg)
```

```json
// Response 200
{
  "sku_id": 42,
  "level": "sgg",
  "regions": [
    { "sgg_id": 1, "name": "강남구", "avg_price": 1020000, "listing_count": 8 },
    { "sgg_id": 2, "name": "서초구", "avg_price": 1005000, "listing_count": 5 }
  ]
}
```

---

## 7. 분석 (Analytics)

> `/analytics/summary`는 sku_id + region_id 기반으로 동작.
> 텍스트 스펙을 직접 받던 이전 방식 대신, `/sku/resolve` → sku_id 획득 후 호출.

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/analytics/summary` | 통합 시세 분석 | ✗ |
| GET | `/analytics/listings` | 최저가 매물 목록 (페이지네이션) | ✗ |
| GET | `/analytics/trending` | 최근 급등/급락 SKU 목록 (홈 피드용) | ✗ |
| GET | `/analytics/popular` | 인기 스펙 Top N | ✗ |
| GET | `/analytics/platform-compare` | 플랫폼별 평균가 비교 | ✗ |

### GET `/analytics/summary`
```
Query params:
  sku_id=42
  region_id=42    (emd.region_id, 생략 시 서울 전체)
```

```json
// Response 200
{
  "sku_id": 42,
  "label": "iPhone 15 Pro 256GB 자연색 티타늄",
  "region": "서울특별시 강남구 역삼동",
  "summary": {
    "avg_price": 1050000,
    "min_price": 850000,
    "max_price": 1300000,
    "listing_count": 42,
    "updated_at": "2026-05-31T00:00:00+09:00"
  },
  "price_trend": {
    "period": "4w",
    "change_rate": -2.5,
    "chart_data": [
      { "bucket_ts": "2026-05-03", "avg_price": 1100000 },
      { "bucket_ts": "2026-05-24", "avg_price": 1050000 }
    ]
  },
  "regional_breakdown": [
    { "sgg": "강남구", "emd": "역삼동", "avg_price": 1020000, "listing_count": 8 }
  ]
}
```

### GET `/analytics/listings`
```
Query params:
  sku_id=42
  region_id=42        (emd.region_id, 생략 시 서울 전체)
  page=1
  page_size=20
  sort=price_asc      (price_asc | price_desc | newest)
  source=daangn       (daangn | bunjang | joongna, 생략 시 전체)
```

```json
// Response 200
{
  "total": 152,
  "page": 1,
  "page_size": 20,
  "listings": [
    {
      "item_id": 10001,
      "listing_price": 850000,
      "title": "아이폰 15 프로 256 자연색 팝니다",
      "sgg": "강남구",
      "emd": "역삼동",
      "source": "daangn",
      "source_url": "https://...",
      "status": "active",
      "created_at": "2026-05-30T14:00:00+09:00"
    }
  ]
}
```

### GET `/analytics/trending`
```
Query params:
  category_id=1   (생략 시 전체)
  limit=10
  direction=drop  (drop | rise | both, 기본 both)
```

```json
// Response 200
{
  "trending": [
    {
      "sku_id": 42,
      "label": "iPhone 15 Pro 256GB 자연색 티타늄",
      "avg_price": 1050000,
      "change_rate": -5.2,
      "direction": "drop"
    }
  ]
}
```

### GET `/analytics/popular`
```
Query params:
  category_id=1
  limit=10
```

```json
// Response 200
{
  "popular": [
    {
      "sku_id": 42,
      "label": "iPhone 15 Pro 256GB 자연색 티타늄",
      "avg_price": 1050000,
      "search_count": 312
    }
  ]
}
```

### GET `/analytics/platform-compare`
```
Query params:
  sku_id=42
  region_id=42    (생략 시 서울 전체)
```

```json
// Response 200
{
  "sku_id": 42,
  "platforms": [
    { "source": "daangn", "avg_price": 1020000, "listing_count": 20 },
    { "source": "bunjang", "avg_price": 1060000, "listing_count": 15 },
    { "source": "joongna", "avg_price": 1080000, "listing_count": 7 }
  ]
}
```

---

## 8. 매물 (Items)

> Alert에서 item_id를 FK로 참조하므로 단건 조회 엔드포인트 필요.

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/items/{item_id}` | 매물 상세 단건 조회 | ✗ |
| GET | `/items/{item_id}/similar` | 같은 SKU의 유사 매물 목록 | ✗ |

### GET `/items/{item_id}`
```json
// Response 200
{
  "item_id": 10001,
  "sku_id": 42,
  "label": "iPhone 15 Pro 256GB 자연색 티타늄",
  "title": "아이폰 15 프로 256 자연색 팝니다",
  "price": 850000,
  "status": "active",
  "region": { "sgg": "강남구", "emd": "역삼동" },
  "source": "daangn",
  "source_url": "https://...",
  "created_at": "2026-05-30T14:00:00+09:00",
  "updated_at": "2026-05-31T00:00:00+09:00"
}
```

### GET `/items/{item_id}/similar`
```
Query params:
  limit=10
  sort=price_asc
```

```json
// Response 200
{
  "sku_id": 42,
  "items": [
    {
      "item_id": 10002,
      "price": 870000,
      "sgg": "서초구",
      "source": "bunjang",
      "source_url": "https://..."
    }
  ]
}
```

---

## 9. 찜 (Watchlist)

> 로그인 사용자가 관심 스펙+지역 저장 + max_price 설정 → 가격 알림 트리거.

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/watchlist` | 내 찜 목록 | ✓ |
| POST | `/watchlist` | 찜 추가 | ✓ |
| GET | `/watchlist/{watch_id}` | 찜 단건 조회 | ✓ |
| PATCH | `/watchlist/{watch_id}` | 찜 수정 | ✓ |
| PATCH | `/watchlist/{watch_id}/active` | 활성/비활성 토글 | ✓ |
| DELETE | `/watchlist/{watch_id}` | 찜 삭제 | ✓ |
| GET | `/watchlist/{watch_id}/alerts` | 해당 찜에서 발생한 알림 목록 | ✓ |

### GET `/watchlist`
```json
// Response 200
{
  "watchlist": [
    {
      "watch_id": 7,
      "sku_id": 42,
      "label": "15프로 256 찾는 중",
      "product": "iPhone",
      "spec_label": "iPhone 15 Pro 256GB",
      "region": { "sgg": "강남구" },
      "max_price": 950000,
      "is_active": true,
      "alert_channels": ["email", "sms"],
      "latest_alert": {
        "alert_id": 22,
        "triggered_at": "2026-05-31T06:00:00+09:00",
        "is_read": false
      },
      "created_at": "2026-05-31T12:00:00+09:00"
    }
  ]
}
```

### POST `/watchlist`
```json
// Request
{
  "sku_id": 42,
  "region_id": 42,
  "max_price": 950000,
  "label": "15프로 256 찾는 중",
  "alert_channels": ["email", "sms"]
}

// Response 201
{
  "watch_id": 7,
  "sku_id": 42,
  "label": "15프로 256 찾는 중",
  "region_id": 42,
  "max_price": 950000,
  "is_active": true,
  "alert_channels": ["email", "sms"],
  "created_at": "2026-05-31T12:00:00+09:00"
}
```

### GET `/watchlist/{watch_id}`
```json
// Response 200
// POST /watchlist 응답과 동일한 구조 + spec 상세 포함
{
  "watch_id": 7,
  "sku_id": 42,
  "spec_label": "iPhone 15 Pro 256GB 자연색 티타늄",
  "attributes": [
    { "code": "model", "value": "iPhone 15 Pro" },
    { "code": "storage", "value": "256GB" }
  ],
  "region": { "sd": "서울특별시", "sgg": "강남구" },
  "max_price": 950000,
  "is_active": true,
  "alert_channels": ["email", "sms"],
  "created_at": "2026-05-31T12:00:00+09:00",
  "updated_at": "2026-05-31T12:00:00+09:00"
}
```

### PATCH `/watchlist/{watch_id}`
```json
// Request (변경할 필드만)
{ "max_price": 900000, "alert_channels": ["email"] }
```

### PATCH `/watchlist/{watch_id}/active`
```json
// Response 200
{ "watch_id": 7, "is_active": false }
```

### GET `/watchlist/{watch_id}/alerts`
```
Query params:
  page=1
  page_size=20
```

```json
// Response 200
{
  "watch_id": 7,
  "total": 5,
  "alerts": [
    {
      "alert_id": 22,
      "message": "iPhone 15 Pro 256GB — 강남구에 840,000원 매물이 등록되었습니다.",
      "item_id": 10055,
      "listing_price": 840000,
      "is_read": false,
      "triggered_at": "2026-05-31T06:00:00+09:00"
    }
  ]
}
```

---

## 10. 알림 (Alerts)

> 스케줄러가 watchlist 순회 → max_price 이하 매물 발생 시 alert 생성.
> 채널: **인앱(DB)** + **이메일** + **SMS** (사용자 인증 완료 + 구독 설정 시)

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/alerts` | 내 알림 목록 (최신순, 필터 가능) | ✓ |
| GET | `/alerts/unread-count` | 읽지 않은 알림 수 | ✓ |
| PATCH | `/alerts/{alert_id}/read` | 알림 읽음 처리 | ✓ |
| PATCH | `/alerts/read-all` | 전체 읽음 처리 | ✓ |
| DELETE | `/alerts/{alert_id}` | 알림 단건 삭제 | ✓ |
| DELETE | `/alerts` | 알림 전체 삭제 (bulk) | ✓ |

### GET `/alerts`
```
Query params:
  is_read=false       (true | false, 생략 시 전체)
  watch_id=7          (특정 찜 필터)
  from=2026-05-01     (ISO 8601 날짜)
  page=1
  page_size=20
```

```json
// Response 200
{
  "total": 3,
  "unread": 2,
  "alerts": [
    {
      "alert_id": 22,
      "watch_id": 7,
      "watch_label": "15프로 256 찾는 중",
      "spec_label": "iPhone 15 Pro 256GB",
      "message": "iPhone 15 Pro 256GB — 강남구에 840,000원 매물이 등록되었습니다.",
      "item": {
        "item_id": 10055,
        "listing_price": 840000,
        "source": "daangn",
        "source_url": "https://..."
      },
      "is_read": false,
      "triggered_at": "2026-05-31T06:00:00+09:00"
    }
  ]
}
```

### DELETE `/alerts`
```json
// Request (생략 시 전체 삭제)
{ "alert_ids": [22, 23, 24] }

// Response 200
{ "deleted_count": 3 }
```

---

## 11. 검색 (Search)

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/search/autocomplete` | 모델명 자동완성 | ✗ |

### GET `/search/autocomplete`
```
Query params:
  q=아이폰15
  category_id=1   (생략 시 전체)
  limit=10
```

```json
// Response 200
{
  "suggestions": [
    { "sku_id": 42, "label": "iPhone 15 Pro 256GB 자연색 티타늄", "category": "iPhone" },
    { "sku_id": 43, "label": "iPhone 15 Pro 128GB 자연색 티타늄", "category": "iPhone" }
  ]
}
```

---

## 12. 서비스 통계 (Stats)

> 홈화면 배너, 마지막 업데이트 안내 등 공개 정보.

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/stats` | 서비스 공개 통계 | ✗ |

### GET `/stats`
```json
// Response 200
{
  "total_listings": 125430,
  "total_skus": 312,
  "last_crawled_at": "2026-05-31T06:00:00+09:00",
  "platforms": {
    "daangn": { "listing_count": 60000, "last_crawled_at": "2026-05-31T06:00:00+09:00" },
    "bunjang": { "listing_count": 40000, "last_crawled_at": "2026-05-31T06:05:00+09:00" },
    "joongna": { "listing_count": 25430, "last_crawled_at": "2026-05-31T06:10:00+09:00" }
  }
}
```

---

## 13. 관리자 (Admin)

> 별도 인증 필요 (admin role 확인). 모든 엔드포인트 `✓ (admin)`.
> Base: `/api/v1/admin`

| Method | Path | 설명 |
|--------|------|------|
| GET | `/admin/stats` | 전체 서비스 통계 (유저 수 포함) |
| GET | `/admin/crawlers/status` | 플랫폼별 크롤러 최근 실행 결과 |
| POST | `/admin/crawlers/{platform}/trigger` | 수동 크롤링 트리거 — platform: `daangn` \| `bunjang` \| `joongna` |
| GET | `/admin/scheduler/jobs` | APScheduler 잡 목록 + 다음 실행 시각 |
| GET | `/admin/users` | 사용자 목록 (페이지네이션, 이메일/닉네임 검색) |
| PATCH | `/admin/users/{user_id}/status` | 사용자 정지/복구 |
| GET | `/admin/categories` | 카테고리 + 속성 관리 목록 |
| POST | `/admin/categories/{category_id}/attributes` | 카테고리에 속성 추가 |

### GET `/admin/stats`
```json
// Response 200
{
  "users": { "total": 1500, "active_today": 230, "deleted": 12 },
  "listings": { "total": 125430, "added_today": 3200 },
  "watchlists": { "total": 4800, "active": 4200 },
  "alerts_sent_today": 320
}
```

### GET `/admin/crawlers/status`
```json
// Response 200
{
  "crawlers": [
    {
      "platform": "daangn",
      "last_run_at": "2026-05-31T06:00:00+09:00",
      "status": "success",
      "items_upserted": 1200,
      "duration_sec": 45
    },
    {
      "platform": "bunjang",
      "last_run_at": "2026-05-31T06:05:00+09:00",
      "status": "partial_fail",
      "items_upserted": 800,
      "error": "timeout on page 5"
    }
  ]
}
```

### POST `/admin/crawlers/{platform}/trigger`
```json
// Response 202
{ "message": "daangn 크롤링이 시작되었습니다.", "job_id": "crawl-daangn-20260531" }
```

### GET `/admin/scheduler/jobs`
```json
// Response 200
{
  "jobs": [
    {
      "job_id": "crawl_all",
      "name": "전체 크롤링",
      "cron": "0 6 * * *",
      "next_run_at": "2026-06-01T06:00:00+09:00",
      "status": "active"
    },
    {
      "job_id": "alert_check",
      "name": "가격 알림 체크",
      "cron": "30 6 * * *",
      "next_run_at": "2026-06-01T06:30:00+09:00",
      "status": "active"
    }
  ]
}
```

### GET `/admin/users`
```
Query params:
  q=변민규          (이메일 or 닉네임 검색)
  status=active     (active | deleted | suspended)
  page=1
  page_size=20
```

```json
// Response 200
{
  "total": 1500,
  "users": [
    {
      "user_id": 1,
      "email": "user@example.com",
      "nickname": "변민규",
      "is_email_verified": true,
      "status": "active",
      "created_at": "2026-05-01T00:00:00+09:00"
    }
  ]
}
```

### PATCH `/admin/users/{user_id}/status`
```json
// Request
{ "status": "suspended", "reason": "어뷰징 의심" }
// Response 200
{ "user_id": 1, "status": "suspended" }
```

---

## 14. 시스템 (System)

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/health` | 헬스체크 (DB·크롤러 상태 포함) | ✗ |

### GET `/health`
```json
// Response 200
{
  "status": "ok",
  "db": "ok",
  "scheduler": "ok",
  "version": "1.0.0",
  "timestamp": "2026-05-31T12:00:00+09:00"
}

// Response 503 (일부 장애)
{
  "status": "degraded",
  "db": "ok",
  "scheduler": "error",
  "timestamp": "2026-05-31T12:00:00+09:00"
}
```

---

## 엔드포인트 수 요약

| 그룹 | 엔드포인트 수 |
|------|--------------|
| Auth | 9 |
| Users | 8 |
| Verifications | 4 |
| Categories | 2 |
| Regions | 3 |
| SKU | 4 |
| Analytics | 5 |
| Items | 2 |
| Watchlist | 7 |
| Alerts | 6 |
| Search | 1 |
| Stats | 1 |
| Admin | 8 |
| System | 1 |
| **합계** | **61** |

---

## 미결 사항 (TODO)

- [ ] SMS 제공사 선택: 네이버 클라우드 SENS vs 카카오 알림톡 vs Twilio
- [ ] 소셜 로그인 (카카오/애플) — 엔드포인트 설계 완료, OAuth 앱 등록 필요
- [ ] refresh token DB 저장 vs Redis — 현재는 DB로 진행
- [ ] 가격 알림 스케줄러 주기: 크롤링 직후 1회 → 매일 00:00
- [ ] 탈퇴 후 30일 완전 삭제 배치 작업 (`/admin/scheduler/jobs`에 추가)
- [ ] Rate Limiting 구현 방식: slowapi (in-process) vs nginx 레벨
- [ ] Admin 인증 방식: 별도 JWT role vs 분리된 admin 계정 테이블
- [ ] `/analytics/popular` 조회수 집계 방식 결정 (별도 로그 테이블 vs Redis counter)
