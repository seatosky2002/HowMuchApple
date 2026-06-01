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

---

## 2. 사용자 (Users)

> 보안: URL에 user_id 노출 없이 토큰으로 본인 식별 (`/me` 패턴).

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/users/me` | 내 프로필 조회 | ✓ |
| PATCH | `/users/me` | 내 정보 수정 (닉네임, 알림 수단 등) | ✓ |
| DELETE | `/users/me` | 회원 탈퇴 (Soft Delete) | ✓ |
| POST | `/users/check-email` | 이메일 중복 확인 | ✗ |
| POST | `/users/check-nickname` | 닉네임 중복 확인 | ✗ |

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
  "phone": "010-****-5678",    // 인증된 경우만
  "created_at": "2026-05-31T12:00:00+09:00"
}
```

### PATCH `/users/me`
```json
// Request (변경할 필드만)
{
  "nickname": "새닉네임",
  "alert_channels": { "email": true, "sms": true }
}
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

## 4. 카탈로그 (Products)

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/products` | 지원 제품 목록 | ✗ |
| GET | `/products/{product}/options` | 스펙 옵션 목록 (드롭다운용) | ✗ |

### GET `/products`
```json
{ "products": ["iPhone", "iPad", "MacBook", "AppleWatch", "AirPods"] }
```

### GET `/products/{product}/options`
```json
// GET /products/iPhone/options
{
  "product": "iPhone",
  "options": {
    "model": ["iPhone 15", "iPhone 15 Pro", "iPhone 14", ...],
    "storage": ["128GB", "256GB", "512GB"],
    "color": ["자연색 티타늄", "블루 티타늄", ...]
  }
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

## 6. 분석 (Analytics)

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| POST | `/analytics/summary` | 통합 시세 분석 | ✗ |
| GET | `/analytics/listings` | 최저가 매물 목록 (페이지네이션) | ✗ |

### POST `/analytics/summary`
```json
// Request
{
  "product": "iPhone",
  "spec": { "model": "iPhone 15 Pro", "storage": "256GB", "color": "자연색 티타늄" },
  "region": { "sd": "서울특별시", "sgg": "강남구", "emd": "역삼동" }
}

// Response 200
{
  "status": "success",
  "data": {
    "summary_info": {
      "model_name": "iPhone 15 Pro 256GB 자연색 티타늄",
      "average_price": 1050000,
      "highest_listing_price": 1300000,
      "lowest_listing_price": 850000,
      "listing_count": 42,
      "data_date": "2026-05-31T00:00:00+09:00"
    },
    "regional_analysis": {
      "detail_by_district": [
        { "sgg": "강남구", "emd": "역삼동", "average_price": 1020000, "listing_count": 8 }
      ]
    },
    "price_trend": {
      "trend_period": 4,
      "change_rate": -2.5,
      "chart_data": [
        { "period": "2026-05-03", "price": 1100000 },
        { "period": "2026-05-10", "price": 1080000 },
        { "period": "2026-05-17", "price": 1060000 },
        { "period": "2026-05-24", "price": 1050000 }
      ]
    }
  }
}
```

### GET `/analytics/listings`
```
Query params:
  product=iPhone
  model=iPhone+15+Pro
  storage=256GB
  region_id=42        (emd.region_id, 생략 시 서울 전체)
  page=1
  page_size=20
  sort=price_asc      (price_asc | price_desc | newest)
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
      "source_url": "https://..."
    }
  ]
}
```

---

## 7. 찜 (Watchlist)

> 로그인 사용자가 관심 스펙+지역 저장 + max_price 설정 → 가격 알림 트리거.

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/watchlist` | 내 찜 목록 | ✓ |
| POST | `/watchlist` | 찜 추가 | ✓ |
| PATCH | `/watchlist/{watch_id}` | 찜 수정 | ✓ |
| DELETE | `/watchlist/{watch_id}` | 찜 삭제 | ✓ |

### POST `/watchlist`
```json
// Request
{
  "product": "iPhone",
  "spec": { "model": "iPhone 15 Pro", "storage": "256GB" },
  "region": { "sd": "서울특별시", "sgg": "강남구" },
  "max_price": 950000,
  "label": "15프로 256 찾는 중",
  "alert_channels": ["email", "sms"]   // 이 찜에 한해 알림 채널 선택
}

// Response 201
{
  "watch_id": 7,
  "product": "iPhone",
  "spec": { "model": "iPhone 15 Pro", "storage": "256GB" },
  "region": { "sd": "서울특별시", "sgg": "강남구" },
  "max_price": 950000,
  "label": "15프로 256 찾는 중",
  "alert_channels": ["email", "sms"],
  "created_at": "2026-05-31T12:00:00+09:00"
}
```

### PATCH `/watchlist/{watch_id}`
```json
// Request (변경할 필드만)
{ "max_price": 900000, "alert_channels": ["email"] }
```

---

## 8. 알림 (Alerts)

> 스케줄러가 watchlist 순회 → max_price 이하 매물 발생 시 alert 생성.
> 채널: **인앱(DB)** + **이메일** + **SMS** (사용자 인증 완료 + 구독 설정 시)

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| GET | `/alerts` | 내 알림 목록 (최신순) | ✓ |
| GET | `/alerts/unread-count` | 읽지 않은 알림 수 | ✓ |
| PATCH | `/alerts/{alert_id}/read` | 알림 읽음 처리 | ✓ |
| PATCH | `/alerts/read-all` | 전체 읽음 처리 | ✓ |
| DELETE | `/alerts/{alert_id}` | 알림 삭제 | ✓ |

### GET `/alerts`
```json
// Response 200
{
  "total": 3,
  "unread": 2,
  "alerts": [
    {
      "alert_id": 22,
      "watch_id": 7,
      "label": "15프로 256 찾는 중",
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

---

## 미결 사항 (TODO)

- [ ] SMS 제공사 선택: 네이버 클라우드 SENS vs 카카오 알림톡 vs Twilio
- [ ] 소셜 로그인 (카카오/애플) 추가 여부
- [ ] refresh token DB 저장 vs Redis — 현재는 DB로 진행
- [ ] 가격 알림 스케줄러 주기: 크롤링 직후 1회 → 매일 00:00
- [ ] 탈퇴 후 30일 완전 삭제 배치 작업 추가 여부
- [ ] Rate Limiting 구현 방식: slowapi (in-process) vs nginx 레벨
