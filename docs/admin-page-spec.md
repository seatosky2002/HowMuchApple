# Admin 관리 페이지 스펙

> 작성일: 2026-07-05 · 상태: Draft

## 1. 개요

HowMuchApple 운영자를 위한 관리 페이지. 핵심 가치는 **크롤러 상태 모니터링과 데이터 품질 관리**다.
이 서비스는 크롤러가 멈추면 데이터가 들어오지 않는 구조이므로, 크롤러의 건강 상태를 한눈에 보고
즉시 대응(수동 실행, 타겟 수정)할 수 있어야 한다.

### 목표

- 서비스 현황(유저/매물/알림)을 대시보드로 파악
- 크롤러 실행 상태·이력 모니터링 및 수동 트리거
- 크롤링 타겟(모델/키워드)을 코드 배포 없이 관리
- 수집 데이터 품질 관리 (SKU/지역 미매칭 매물 처리)
- 유저 관리 (검색, 정지/해제)
- 알림 발송 현황 모니터링

### 비범위 (Non-goals)

- 크롤러 스케줄(cron) 변경 UI — env로 관리 유지
- 매물 데이터 직접 수정(가격/제목 편집) — 숨김/SKU 재지정만 허용
- 통계 차트 고도화 — 1차는 숫자 카드 위주
- SMS 발송 (백엔드가 스텁 상태)

---

## 2. 권한 및 보안

### 2.1 백엔드 (대부분 구현됨)

- 모든 admin API는 `Depends(get_current_admin)` 필수 — `users.is_admin` 검사 (`app/core/dependencies.py:33`)
- 관리자 지정은 당분간 DB 직접 수정 (`UPDATE users SET is_admin = 1 WHERE ...`)

### 2.2 프론트엔드 (신규)

- `/admin/*` 라우트 전체에 `AdminRoute` 가드 컴포넌트 적용
  - 비로그인 → `/login` 리다이렉트
  - 로그인 + `is_admin == false` → `/` 리다이렉트 (admin 페이지 존재 자체를 숨김)
- 일반 유저 UI(Layout 네비게이션)에는 admin 링크를 노출하지 않음. `is_admin`인 경우에만 표시.

### 2.3 선행 수정 필요 ⚠️

| # | 항목 | 위치 | 내용 |
|---|---|---|---|
| 1 | `/users/me`에 `is_admin` 노출 | `schemas/user.py`, `services/user.py` | 현재 응답에 없음 → 프론트가 관리자 여부를 알 수 없음. `UserMeResponse`에 `is_admin: bool` 추가 |
| 2 | 크롤러 수동 트리거 버그 | `endpoints/admin.py:154` | request-scoped `db` 세션을 `asyncio.create_task`에 전달 → 응답 후 세션이 닫혀 크롤러 실패. 백그라운드 태스크 내부에서 `AsyncSessionLocal()`로 새 세션 생성 + 태스크 참조 유지로 수정 |

---

## 3. 정보 구조 (IA)

```
/admin
├── /admin              대시보드 (홈)
├── /admin/crawlers     크롤러 관리 (상태 + 로그 이력 + 수동 실행)
├── /admin/targets      크롤링 타겟 관리
├── /admin/items        매물 관리 (데이터 품질)
├── /admin/users        유저 관리
├── /admin/alerts       알림 발송 현황
└── /admin/categories   카테고리/속성 관리
```

레이아웃: 좌측 사이드바(메뉴) + 우측 콘텐츠. 기존 서비스 Layout과 분리된 `AdminLayout` 신규 작성.

---

## 4. 화면별 상세

### 4.1 대시보드 — `/admin`

서비스 전체 현황 요약. 진입 시 가장 먼저 보는 화면.

**구성**

| 섹션 | 내용 | API |
|---|---|---|
| 유저 카드 | 총 유저 / 오늘 활성 / 탈퇴 | `GET /api/v1/admin/stats` ✅ 기존 |
| 매물 카드 | 총 매물 / 오늘 추가 | 〃 |
| 워치리스트 카드 | 총 등록 / 활성 | 〃 |
| 알림 카드 | 오늘 발송 건수 | 〃 |
| 시스템 상태 | DB·스케줄러 ok/error 뱃지 | `GET /health` ✅ 기존 |
| 크롤러 요약 | 플랫폼별 마지막 실행 상태 (성공/실패 뱃지) — 클릭 시 `/admin/crawlers` 이동 | `GET /api/v1/admin/crawlers/status` ✅ 기존 |

**백엔드 변경**

- `admin/stats`의 `active_today`가 항상 0 (TODO 방치, `admin.py:88`) → 1차에서는 카드에서 제외하거나 "미집계" 표기. `users.last_login_at` 컬럼 추가는 2차.

---

### 4.2 크롤러 관리 — `/admin/crawlers`

**(a) 현재 상태 패널** — 플랫폼(당근/번개장터/중고나라)별 카드

- 마지막 실행 시각, 상태(success/fail/running), 수집 개수, 소요 시간, 에러 메시지(실패 시)
- [지금 실행] 버튼 → `POST /api/v1/admin/crawlers/{platform}/trigger` ✅ 기존 (⚠️ 2.3-2 버그 수정 선행)
  - 실행 중일 때는 버튼 비활성 + "실행 중" 표시 (최근 로그 status가 `running`이면 비활성)
- 스케줄 정보: `GET /api/v1/admin/scheduler/jobs` ✅ 기존 — 다음 실행 시각 표시

**(b) 실행 로그 이력 테이블** 🆕

- 컬럼: 실행 시각, 플랫폼, 상태, 수집 개수, 소요 시간, 에러 메시지(축약, hover로 전체)
- 필터: 플랫폼, 상태(success/fail), 기간
- 페이지네이션 (기본 20건)

**신규 API**

```
GET /api/v1/admin/crawlers/logs
  ?platform=daangn&status=fail&page=1&page_size=20
→ 200 {
  "total": 123,
  "logs": [{
    "log_id": 1, "platform": "daangn", "status": "success",
    "items_upserted": 42, "duration_sec": 180,
    "error": null, "started_at": "...", "finished_at": "..."
  }]
}
```

- 데이터는 기존 `crawler_log` 테이블 그대로 사용. DB 변경 없음.

---

### 4.3 크롤링 타겟 관리 — `/admin/targets` 🆕

현재 타겟이 `app/crawlers/targets.py`에 하드코딩되어 있어 신모델 추가 시마다 코드 배포가 필요하다.
DB로 이전하여 admin에서 관리한다.

**DB 변경 — `crawl_target` 테이블 신규**

| 컬럼 | 타입 | 설명 |
|---|---|---|
| target_id | INT PK AUTO_INCREMENT | |
| category | VARCHAR(50) | "iPhone" / "iPad" / "MacBook" ... (category 테이블 name과 일치) |
| model | VARCHAR(100) | "iPhone 16 Pro" |
| released_year | SMALLINT | 2024 |
| primary_keyword | VARCHAR(100) | "아이폰 16 프로" |
| aliases | JSON | ["아이폰16프로", "iPhone 16 Pro"] |
| is_active | BOOLEAN DEFAULT 1 | 비활성 시 크롤링 제외 |
| sort_order | INT DEFAULT 0 | |
| created_at / updated_at | DATETIME | |

- Alembic 마이그레이션에서 기존 `CRAWL_TARGETS` 상수를 시드 데이터로 삽입
- 크롤러(`BaseCrawler.__init__`)는 DB에서 `is_active=1`인 타겟을 로드하도록 변경.
  DB 조회 실패 또는 0건이면 기존 `CRAWL_TARGETS` 상수로 폴백 (크롤링 중단 방지)
- `targets.py`의 `CrawlTarget` dataclass와 상수는 폴백/시드용으로 유지

**화면**

- 테이블: 카테고리, 모델, 출시연도, 대표 키워드, 별칭 수, 활성 여부 토글, 수정/삭제
- 필터: 카테고리, 활성 여부 / 정렬: 카테고리 → sort_order
- [타겟 추가] 모달: category(셀렉트), model, released_year, primary_keyword, aliases(태그 입력)
- 활성 토글은 즉시 반영 (PATCH)
- 삭제는 컨펌 모달 (수집된 매물은 유지됨을 안내)

**신규 API**

```
GET    /api/v1/admin/targets?category=iPhone&is_active=true&page=1&page_size=50
POST   /api/v1/admin/targets          # {category, model, released_year, primary_keyword, aliases[]}
PATCH  /api/v1/admin/targets/{id}     # 부분 수정 (is_active 토글 포함)
DELETE /api/v1/admin/targets/{id}
```

- POST/PATCH 검증: (category, model) 조합 중복 시 409, aliases 내 중복 제거

---

### 4.4 매물 관리 — `/admin/items` 🆕

크롤링 데이터 품질 관리. 핵심 유스케이스는 **분류 실패 매물 찾기**다.

**요약 카드 (상단)**

- 전체 매물 수 / SKU 미매칭 수 / 지역 미매칭 수 / 오늘 수집 수

**테이블**

- 컬럼: item_id, 제목(원본 링크), 가격, 플랫폼, SKU 라벨(미매칭 시 ⚠️ 뱃지), 지역(미매칭 시 ⚠️), 상태, 수집일
- 필터:
  - `matched=unmatched_sku` — sku_id IS NULL (크롤러가 모델 분류 실패)
  - `matched=unmatched_region` — emd_id IS NULL (지역 파싱 실패)
  - 플랫폼(source), 상태(active/sold/deleted), 검색어(제목), 기간
- 정렬: 최신순(기본), 가격순

**액션**

- 상태 변경: active ↔ deleted (잘못 수집된 매물 숨김). `deleted`는 소프트 삭제 — 통계/알림에서 제외됨 (기존 쿼리들이 `status == active` 필터를 이미 사용)
- SKU 재지정: SKU 검색 모달(기존 `GET /api/v1/search/autocomplete` 재사용)에서 선택 → item.sku_id 갱신

**신규 API**

```
GET   /api/v1/admin/items
  ?matched=unmatched_sku&source=daangn&status=active&q=아이폰&page=1&page_size=20
→ 200 { "total": n, "summary": {"total": n, "unmatched_sku": n, "unmatched_region": n, "added_today": n}, "items": [...] }

PATCH /api/v1/admin/items/{item_id}    # {status?: "active"|"deleted", sku_id?: int|null}
```

---

### 4.5 유저 관리 — `/admin/users`

**전부 기존 API로 구현 가능** ✅

- 테이블: user_id, 이메일, 닉네임, 이메일 인증 여부, 상태(active/suspended/deleted), 가입일
- 검색(이메일/닉네임), 상태 필터, 페이지네이션 — `GET /api/v1/admin/users`
- [정지]/[해제] 버튼 (컨펌 모달) — `PATCH /api/v1/admin/users/{id}/status`
- 탈퇴(deleted) 유저는 읽기 전용 표시

**정책**

- 자기 자신 정지 방지: 백엔드에 가드 추가 (`user_id == current_admin.user_id` → 400) 🆕 소규모 수정

---

### 4.6 알림 발송 현황 — `/admin/alerts` 🆕

가격 알림이 실제로 나가고 있는지 모니터링. `alert` 테이블의 `sent_email`/`sent_sms` 플래그를 활용한다.

**요약 카드**

- 오늘 생성된 알림 수 / 이메일 발송 성공 수 / 이메일 발송 실패 수(생성됐지만 sent_email=false인 것 중 이메일 수신 설정 유저 대상) / 최근 7일 추이(숫자)

**테이블**

- 컬럼: alert_id, 유저(이메일), 메시지(축약), 매물 링크, sent_email ✓/✗, 생성 시각
- 필터: 발송 성공/실패, 기간
- 페이지네이션

**신규 API**

```
GET /api/v1/admin/alerts
  ?sent_email=false&from=2026-07-01&page=1&page_size=20
→ 200 {
  "total": n,
  "summary": {"created_today": n, "email_sent_today": n, "email_failed_today": n},
  "alerts": [{"alert_id", "user_email", "message", "item_id", "source_url", "sent_email", "sent_sms", "triggered_at"}]
}
```

**알려진 한계 (스펙에 명시)**

- 현재 이메일 발송은 동기 smtplib라 이벤트 루프를 블로킹함 (`services/notification.py:23`). 발송량 증가 전에 `asyncio.to_thread` 래핑 필요 — 본 스펙 범위 밖, 별도 이슈로 관리
- 실패 사유(에러 메시지)는 저장 안 됨. 1차는 성공/실패 플래그만 노출, 사유 컬럼은 2차

---

### 4.7 카테고리/속성 관리 — `/admin/categories`

**기존 API로 구현 가능** ✅

- 카테고리 목록 + 각 카테고리의 속성(용량/색상 등) 아코디언 — `GET /api/v1/admin/categories`
- [속성 추가] 모달: 기존 속성 연결(attribute_id) 또는 신규 생성(code/label/datatype/unit/options) — `POST /api/v1/admin/categories/{id}/attributes`
- 속성 수정/삭제는 비범위 (SKU 데이터 정합성 이슈, 2차)

---

## 5. 신규/변경 API 요약

| 메서드 | 경로 | 상태 | 비고 |
|---|---|---|---|
| GET | `/admin/crawlers/logs` | 🆕 | 크롤러 로그 이력 |
| GET | `/admin/targets` | 🆕 | 타겟 목록 |
| POST | `/admin/targets` | 🆕 | 타겟 추가 |
| PATCH | `/admin/targets/{id}` | 🆕 | 타겟 수정/활성 토글 |
| DELETE | `/admin/targets/{id}` | 🆕 | 타겟 삭제 |
| GET | `/admin/items` | 🆕 | 매물 목록 + 품질 요약 |
| PATCH | `/admin/items/{id}` | 🆕 | 상태 변경 / SKU 재지정 |
| GET | `/admin/alerts` | 🆕 | 알림 발송 현황 |
| GET | `/users/me` | 🔧 | `is_admin` 필드 추가 |
| PATCH | `/admin/users/{id}/status` | 🔧 | 자기 자신 정지 방지 가드 |
| POST | `/admin/crawlers/{platform}/trigger` | 🐛 | 닫힌 세션 버그 수정 |

모든 신규 API는 `Depends(get_current_admin)` 적용.

## 6. DB 변경 요약

| 변경 | 내용 |
|---|---|
| `crawl_target` 테이블 신규 | 4.3 참조. Alembic 마이그레이션 + `CRAWL_TARGETS` 시드 |
| 크롤러 타겟 로딩 변경 | DB 우선, 실패 시 코드 상수 폴백 |

(알림 실패 사유, `users.last_login_at`은 2차로 보류)

## 7. 프론트엔드 신규 파일 (예상)

```
src/components/AdminRoute.jsx        # is_admin 라우트 가드
src/components/AdminLayout.jsx       # 사이드바 레이아웃
src/pages/admin/DashboardPage.jsx
src/pages/admin/CrawlersPage.jsx
src/pages/admin/TargetsPage.jsx
src/pages/admin/ItemsPage.jsx
src/pages/admin/UsersPage.jsx
src/pages/admin/AdminAlertsPage.jsx
src/pages/admin/CategoriesPage.jsx
```

`AuthContext`가 `/users/me`의 `is_admin`을 보관하도록 확장.

## 8. 구현 순서

| Phase | 내용 | 의존성 |
|---|---|---|
| **P0** | 선행 수정: `/users/me`에 `is_admin` 추가, 크롤러 트리거 세션 버그 수정 | — |
| **P1** | AdminRoute/AdminLayout + 대시보드 + 유저 관리 + 카테고리 (전부 기존 API) | P0 |
| **P2** | 크롤러 관리 (상태 패널 + 로그 이력 API + 수동 실행) | P0 |
| **P3** | 크롤링 타겟 관리 (DB 마이그레이션 + CRUD API + 크롤러 로딩 변경) | P2 |
| **P4** | 매물 관리 (품질 필터 + 상태/SKU 액션) | P1 |
| **P5** | 알림 발송 현황 | P1 |

각 Phase는 별도 feature 브랜치(`feat/admin-p1-dashboard` 등)로 진행 → dev PR.

## 9. 열린 질문

1. 관리자 계정 지정 UI가 필요한가? (현재: DB 직접 수정. admin이 admin을 임명하는 기능은 위험해서 1차 제외)
2. 크롤러 로그 보존 기간 — 무한 적재 시 테이블 비대. 90일 이후 삭제 배치 필요 여부
3. 매물 hard delete 허용 여부 — 현재는 소프트 삭제(status=deleted)만
