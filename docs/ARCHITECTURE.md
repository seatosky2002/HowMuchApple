# HowMuchApple 아키텍처

> 2026-07-21 기준. 각 절은 **① 우리가 어떻게 했나 → ② 왜 그렇게 했나 → ③ 업계 표준은 무엇인가 → ④ 다른 옵션은 뭐가 있었나** 순서로 정리한다.

---

## 0. 한눈에 보기

```
[브라우저 (React SPA)]
        │  HTTP (같은 오리진, 쿠키 자동 첨부)
        ▼
[nginx :80] ── 정적 파일(/, /assets) 서빙
        │  └─ /api/* 리버스 프록시
        ▼
[FastAPI :8000 (uvicorn)] ── CORS 미들웨어, 예외 핸들러
        │        └─ APScheduler (매일 15:00 KST 크롤링 → price_stats 스냅샷)
        ▼
[MySQL 8.4] ── item / sku / price_stats / users / refresh_token ...
```

- 배포: Oracle Cloud VM 1대, `docker-compose.nodomain.yml` (mysql, backend, nginx 3컨테이너)
- 코드: `backend/`(FastAPI, SQLAlchemy 2 async), `frontend/`(React + Vite + Tailwind)
- 데이터: 당근/번개장터/중고나라 크롤러가 매물을 수집 → SKU(모델+용량 지문)에 배정 → 시세 통계 제공

---

## 1. API 호출 경로

### ① 어떻게

- 프론트는 axios 인스턴스 하나(`frontend/src/api/client.js`)로 모든 호출을 `baseURL: '/api/v1'` **상대 경로**로 보낸다. `withCredentials: true`로 쿠키를 항상 동봉.
- 개발: Vite dev 서버(5173)가 `/api`를 `localhost:8000`으로 프록시.
- 운영: nginx가 `/api/`를 backend 컨테이너로 프록시(`deploy/nginx/http.conf.template`), 나머지는 SPA 정적 파일 + `try_files ... /index.html` (클라이언트 라우팅 폴백).
- 백엔드 라우팅: `app/api/v1/router.py`에 도메인별 라우터 14개(auth, sku, analytics, watchlist…)를 `/api/v1` prefix로 묶음. 엔드포인트는 얇게 유지하고 로직은 `app/services/`로 분리.

### ② 왜

- **같은 오리진**으로 통일하면 CORS·쿠키 문제(SameSite, 서드파티 쿠키 차단)가 통째로 사라진다. 프론트가 API 주소를 몰라도 되니 환경별 설정도 없다.
- `/api/v1` 버저닝: 클라이언트를 깨지 않고 다음 버전을 병행 배포할 수 있는 가장 저렴한 보험.

### ③ 업계 표준

- SPA + 리버스 프록시(같은 오리진)는 소규모~중규모 서비스의 사실상 표준. URL 경로 버저닝(`/v1`)은 Stripe·GitHub 등 대부분의 공개 API가 쓰는 방식.

### ④ 다른 옵션

| 옵션 | 특징 | 우리가 안 쓴 이유 |
|---|---|---|
| 프론트/백엔드 도메인 분리 + CORS | CDN 배포 유리 | 쿠키 인증과 상성이 나쁨(SameSite=None+Secure 강제), 지금 규모에 이점 없음 |
| BFF(Backend for Frontend) | 클라이언트별 맞춤 API | 클라이언트가 웹 하나뿐 |
| GraphQL | 유연한 쿼리 | 화면-API가 1:1로 단순해서 REST로 충분 |
| 헤더 버저닝(`Accept: ...v2+json`) | URL이 깔끔 | 브라우저/캐시/디버깅에서 경로 버저닝이 압도적으로 편함 |

---

## 2. 미들웨어 스택

### ① 어떻게 (`backend/app/main.py`)

요청이 통과하는 순서대로:

1. **nginx** — gzip 압축, 정적 캐시 정책(아래 §7), 프록시 헤더(X-Real-IP 등) 주입
2. **CORSMiddleware** — `allow_origins=[settings.FRONTEND_URL]`(운영: `http://161.33.29.225`), `allow_credentials=True`
3. **라우터 → Depends 체인** — 인증(`get_current_user`), DB 세션(`get_db`)은 미들웨어가 아니라 **FastAPI 의존성**으로 처리
4. **예외 핸들러** — `AppException`(도메인 예외 계층: NotFound/BadRequest/Unauthorized/Forbidden/Conflict) → 해당 상태코드 + `{"detail": ...}`, 그 외 미처리 예외 → 로그 남기고 일반화된 500 (스택트레이스 비노출)

### ② 왜

- 전역 미들웨어를 최소화하고 **인증을 의존성으로** 푼 것은 FastAPI의 관용 표현이다. 라우트마다 필요한 보호 수준(비로그인/로그인/관리자)을 시그니처에 선언적으로 표시할 수 있고, 공개 엔드포인트(시세 조회)가 인증 코드를 아예 타지 않는다.
- 500 응답을 일반 메시지로 통일한 것은 내부 구조 노출 방지(정보 누출 방어)의 기본.

### ③ 업계 표준

- FastAPI에서 인증·권한은 `Depends` 체인이 표준. Express의 라우트별 미들웨어, Spring Security의 필터 체인과 같은 역할.
- 예외 → HTTP 매핑을 한곳에 모으는 것(도메인 예외 계층)도 표준 패턴.

### ④ 다른 옵션

- **전역 인증 미들웨어 + 화이트리스트**: 모든 요청을 막고 공개 경로만 예외 처리. "기본 차단"이라 안전하지만 경로 목록 관리가 번거롭다. 관리자 API가 늘어나면 고려할 것.
- **TrustedHostMiddleware / ProxyHeadersMiddleware**: 도메인 붙이고 HTTPS 전환 시 추가해야 함(현재 IP 직접 접속이라 생략).

### ⚠️ 현재 상태 주의

`slowapi`(rate limiter)는 `main.py`에서 Limiter 생성과 429 핸들러 등록까지만 되어 있고, **어떤 라우트에도 `@limiter.limit()`이 없으며 SlowAPIMiddleware도 등록되지 않아 실제로는 아무 것도 제한하지 않는다.** §5 참고.

---

## 3. 인증 절차 (JWT + Refresh Token)

### ① 어떻게

**토큰 2종 구조** (`app/core/security.py`, `app/services/auth.py`):

| | access_token | refresh_token |
|---|---|---|
| 형태 | JWT (HS256, `{sub, exp, type:"access"}`) | 불투명 랜덤 문자열 (`secrets.token_urlsafe(64)`) |
| 수명 | 30분 | 14일 |
| 저장(서버) | 없음 (stateless) | **SHA-256 해시만** DB `refresh_token` 테이블에 저장 |
| 저장(클라이언트) | httpOnly 쿠키, `path=/` | httpOnly 쿠키, **`path=/api/v1/auth/refresh`로 제한** |
| 쿠키 속성 | `SameSite=strict`, `secure`(운영 전환 예정) | 동일 |

**로그인 흐름**:
```
POST /auth/login {email, password}
  → bcrypt.checkpw 검증 (실패 시 이메일/비번 어느 쪽이 틀렸는지 구분 안 함)
  → access JWT 발급 + refresh 랜덤 토큰 생성
  → refresh는 해시만 DB 저장, 원문은 쿠키로
  → Set-Cookie 두 개 내려줌 (응답 바디에 토큰 없음)
```

**요청 인증** (`app/core/dependencies.py get_current_user`):
```
쿠키의 access_token → JWT 서명/만료/type 검증 → DB에서 유저 조회
  → 탈퇴(deleted_at)/정지(suspended) 상태 확인 → User 반환
```

**토큰 갱신 — 회전(rotation) + 재사용 감지**:
```
POST /auth/refresh (쿠키 자동 첨부)
  → 해시로 DB 조회 → 유효하면: 기존 레코드 revoke + 새 쌍 발급 (회전)
  → 이미 revoke된 토큰이 또 오면 = 탈취 신호
    → 그 유저의 활성 refresh 토큰 전부 무효화 (전 세션 강제 로그아웃)
```

**부가 흐름**: 카카오 OAuth(인가코드 → 토큰 교환 → 프로필 → 계정 연결/생성), 비밀번호 재설정(이메일 존재 여부 비노출, 1시간짜리 해시 저장 토큰), 탈퇴 후 30일 내 복구.

### ② 왜

- **httpOnly 쿠키**: XSS로 토큰을 탈취할 수 없다(JS에서 접근 불가). SPA에서 토큰을 localStorage에 두는 것보다 안전한 선택.
- **CSRF 방어는 `SameSite=strict`**: 쿠키 인증의 약점인 CSRF를 브라우저 레벨에서 차단. 별도 CSRF 토큰 없이도 크로스사이트 요청에 쿠키가 안 붙는다.
- **refresh를 JWT가 아닌 불투명 토큰 + DB 해시로**: 서버가 개별 세션을 **즉시 무효화**할 수 있다(JWT는 만료 전 강제 취소 불가). 해시만 저장하므로 DB가 유출돼도 토큰 원문을 못 만든다 — 비밀번호를 해시로 저장하는 것과 같은 논리.
- **refresh 쿠키 path 제한**: 갱신 엔드포인트 외의 모든 요청에는 refresh 토큰이 아예 전송되지 않아 노출 표면이 최소화된다.
- **회전 + 재사용 감지**: 탈취범과 정상 사용자 중 한쪽이 회전시키면 다른 쪽의 (구)토큰 사용이 감지되고, 그 순간 전체 세션을 태워버린다.
- **짧은 access(30분) + 긴 refresh(14일)**: stateless 검증의 성능 이점을 누리면서 탈취 피해 시간을 30분으로 제한.
- **bcrypt**: 느리게 설계된 적응형 해시. 로그인 브루트포스 비용을 올린다.

### ③ 업계 표준

- 이 조합 — *짧은 JWT access + 회전하는 refresh + 재사용 감지 + httpOnly/SameSite 쿠키* — 은 **OWASP 권고안 그대로**이며 Auth0 등이 공식 문서에서 권장하는 SPA 인증 패턴이다.
- bcrypt는 여전히 표준권(신규 프로젝트라면 argon2id가 1순위 권고이나 bcrypt도 OWASP 허용 목록).
- "이메일이 존재하면 발송했습니다" 응답(계정 열거 방지)도 표준 관행.

### ④ 다른 옵션

| 옵션 | 장점 | 우리가 안 쓴 이유 |
|---|---|---|
| **localStorage + `Authorization: Bearer`** | CSRF 원천 차단, 구현 단순 | XSS 한 방에 토큰 탈취. 쿠키+SameSite가 더 안전 |
| **서버 세션 (세션ID 쿠키 + Redis)** | 즉시 무효화, 가장 단순한 보안 모델 | 매 요청 세션 저장소 조회. 사실 이 규모엔 이것도 충분했다 — JWT는 확장성 대비 선택 |
| **RS256/EdDSA (비대칭 서명)** | 검증 서버와 발급 서버 분리 가능 | 단일 백엔드라 공개키 배포 이점이 없음. HS256으로 충분 |
| **인증 위임 (Auth0/Cognito/Firebase Auth)** | 구현·운영 부담 제로, MFA 공짜 | 비용, 벤더 종속, 한국 소셜(카카오) 연동은 어차피 직접 작업 |
| **CSRF 토큰(double-submit)** | SameSite 미지원 구형 브라우저 커버 | strict + 최신 브라우저 전제로 생략. 도메인 분리하면 필요해짐 |

### ⚠️ 알려진 갭 (개선 예정 목록)

1. **로그아웃이 서버측 refresh revoke를 안 함** — 쿠키만 지운다(`auth.py`의 `revoke_refresh_token`이 만들어져 있는데 미사용). 탈취된 쿠키 사본이 있으면 로그아웃 후에도 유효.
2. **`COOKIE_SECURE=False`** — 현재 HTTP(IP 접속)라 불가피. 도메인+TLS 전환 시 반드시 True로.
3. **`SECRET_KEY` 기본값 폴백** — `.env` 누락 시 `"change-me-in-production"`으로 뜬다. 기동 시 기본값이면 crash하도록 가드하는 게 안전.
4. **만료 refresh 레코드 청소 없음** — 테이블이 무한히 자란다. 스케줄러에 주기 삭제 잡 추가 필요.
5. **access 토큰마다 DB 유저 조회** — stateless JWT의 이점을 절반만 활용. 규모가 커지면 캐시 또는 클레임 신뢰로 전환.

---

## 4. 인가(Authorization)

- 2단계뿐: 일반 유저(`get_current_user`) / 관리자(`get_current_admin` = `is_admin` 플래그).
- 공개 API(시세·검색·카탈로그)는 의존성 자체를 안 붙인다.
- **표준/대안**: 역할이 늘면 RBAC(role 테이블), 리소스 소유권 검사(지금은 watchlist 등에서 `user_id` 비교로 수행 중)가 다음 단계. Casbin/OPA 같은 정책 엔진은 이 규모엔 과함.

---

## 5. Rate Limit — 현재 미작동, 계획

### ① 현재 상태 (정직하게)

- `slowapi` Limiter가 `main.py`와 `verifications.py`에 **인스턴스만 생성**되어 있고 라우트 적용이 없다. **지금 API 전체가 무제한이다.**
- 그나마 nginx도 `limit_req` 미설정.

### ② 왜 문제인가

- `/verifications/email`·`/phone`은 **실제 메일/SMS 발송**을 트리거한다 → 무한 호출 = 발송 비용 폭탄 + 수신자 스팸.
- `/auth/login` 브루트포스 방어가 bcrypt의 느림 하나뿐.
- 크롤링 데이터 API는 스크래핑 남용에 무방비.

### ③ 업계 표준

- **엣지(nginx) 1차 방어 + 앱 레벨 2차 방어**의 이중 구조가 표준.
  - nginx: `limit_req_zone`(IP 기준, leaky bucket) — 전역 폭주 차단
  - 앱: 엔드포인트 성격별 세밀한 제한(로그인 5/min, 인증코드 3/min, 일반 API 60/min 등), 429 + `Retry-After`
- 다중 인스턴스면 카운터를 **Redis**에 (고정 윈도우/슬라이딩 윈도우/토큰 버킷).

### ④ 옵션 비교

| 옵션 | 적합한 상황 | 비고 |
|---|---|---|
| **slowapi 데코레이터** (현 스택) | 단일 인스턴스, 지금 우리 | 인메모리 카운터. 컨테이너 1개인 지금은 충분 |
| nginx `limit_req` | 전역 IP 폭주 방어 | 앱 배포 없이 설정만으로 추가 가능, 병행 권장 |
| Redis 기반 (slowapi storage 교체) | 백엔드 수평 확장 시 | 지금은 과함 |
| API Gateway (Kong, Cloudflare) | 멀티서비스/대규모 | 인프라 과잉 |

**계획**: 인증코드 발송 3/min, 로그인 5/min, 갱신 10/min을 slowapi 데코레이터로 + nginx에 완만한 전역 limit_req. (이슈로 관리)

---

## 6. 데이터 파이프라인 (크롤링 → 시세)

```
APScheduler (매일 06:00 UTC = 15:00 KST)
  → daangn → bunjang → joongna 순차 크롤 (app/crawlers/)
      ├─ 제목/가격 필터 (filters.py): 악세사리·삽니다·업자·렌탈 글 제거, 카테고리별 가격 상하한
      ├─ SkuAssigner: 제목에서 모델·용량 추출 → fingerprint("1:model=iPhone 17e|storage=256GB")로 SKU 배정
      └─ (source, external_id) 기준 upsert — 기존 매물은 가격/상태 갱신
  → snapshot_price_stats(): (SKU, 읍면동)별 일별 통계를 price_stats에 적재
  → 30분 뒤 가격 알림 잡: watchlist 조건 충족 매물 알림 생성
```

**시세 통계의 이상치 방어 (`get_price_fences`)**: SKU별 활성 매물 가격의 **IQR 펜스**(Q1−1.5·IQR ~ Q3+1.5·IQR, 동일가 밀집 대비 최소 폭 보정)를 계산해 평균/최저/최고·플랫폼 비교·지역별 표·매물 리스트에서 펜스 밖 가격(내구제·계정거래류 비매물 글)을 제외한다.

- **왜 IQR인가**: 키워드 필터는 두더지잡기가 되고, 고정 비율 컷은 SKU마다 시세 스케일이 달라 안 맞는다. IQR은 데이터 분포에 자동 적응하고 표본이 적으면(5개 미만) 필터를 끈다.
- **왜 스냅샷 테이블인가**: 크롤 upsert가 `updated_at`을 매일 덮어써서 item 테이블로는 과거 시세를 복원할 수 없다. 시계열은 적재 시점에 물화(materialize)해야 한다 — 이는 시계열 집계의 일반 원칙.
- **대안**: 매물 이력 테이블(가격 변경마다 행 추가)이 더 정밀하지만 저장량이 크고, 지금 UI(일별 평균)에는 일별 스냅샷이면 충분.

---

## 7. 프론트엔드 & 정적 자산 캐시

- React 19 + Vite + Tailwind, 상태관리 없이 페이지 로컬 state (규모상 Redux/Query 불필요, 필요해지면 TanStack Query 1순위).
- 차트는 라이브러리 없이 인라인 SVG (번들 절약; 요구가 단순 라인 1종).
- **캐시 전략** (한 번 사고 난 뒤 정립됨):
  - `/assets/*` (해시 파일명): `Cache-Control: public, immutable, 30d` — 내용이 바뀌면 파일명이 바뀌므로 영구 캐시 안전
  - `index.html` 및 루트 정적: `Cache-Control: no-cache` — **매번 재검증(304)**. 이게 없으면 배포 후에도 브라우저가 옛 번들을 가리키는 옛 index.html을 씀 (2026-07-21 실제 장애)
- 이 조합(해시 자산 영구 캐시 + 엔트리 no-cache)이 SPA 배포의 업계 표준.

---

## 8. 배포·운영

- **단일 VM + docker compose**: mysql / backend(uvicorn 단일 프로세스 + APScheduler 내장) / nginx.
- 배포 절차: 로컬 검증 → `git push origin main main:feat/deploy-docker`(서버는 feat/deploy-docker 체크아웃) → 서버 `git pull` → 바뀐 서비스만 `build` + `up -d`.
- **개발 워크플로**: 로컬 MySQL(3307) + mock 시더(`scripts/seed_mock_data.py`, 이상치 노이즈와 4주 price_stats 포함 340개 매물 생성) → uvicorn/vite 로컬 기동 → 검증 후 한 번에 배포.
- **왜 이 구성인가**: 트래픽·팀 규모에 맞는 최소 운영 부담. 스케줄러를 API 프로세스에 내장한 것도 같은 이유(프로세스 1개 = 실패 지점 1개).
- **대안과 전환 시점**:
  - uvicorn 워커 다중화/gunicorn: CPU 병목 생기면. 단, 그 순간 APScheduler를 **별도 워커 컨테이너로 분리**해야 함(다중 프로세스에서 중복 실행됨) + rate limit 카운터도 Redis로.
  - k8s/ECS, 관리형 DB(RDS): 지금은 명백한 과잉.
  - CI/CD(GitHub Actions로 push→배포 자동화): 배포 빈도 늘면 1순위 개선.
- **알려진 리스크**: HTTP(무TLS — 도메인 미보유), 단일 VM SPOF, DB 백업 자동화 없음.

---

## 9. 요약: 의도적으로 미룬 것들

| 항목 | 현재 | 전환 트리거 |
|---|---|---|
| rate limit | ❌ 없음 (최우선 부채) | 즉시 — 인증코드/로그인부터 |
| TLS/도메인 | HTTP + IP | 도메인 확보 시 (`docker-compose.prod.yml` + certbot 준비돼 있음) |
| 로그아웃 시 refresh revoke | 쿠키만 삭제 | rate limit과 함께 처리 |
| Redis | 없음 | 백엔드 2인스턴스 or 캐시 필요 시 |
| CI/CD | 수동 ssh 배포 | 배포 주 2회 넘어가면 |
| 모니터링 | 컨테이너 로그뿐 | 유저 생기면 (Sentry 최소 도입) |
