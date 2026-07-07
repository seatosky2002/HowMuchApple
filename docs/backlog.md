# 백로그 & 이슈 트래킹

> 백엔드 코드 리뷰(2026-07-05) 및 이후 작업에서 발견된 이슈 목록.
> GitHub Issues로 이전하기 전까지의 임시 트래킹 문서. 이슈 생성 시 여기서 지우고 링크로 대체할 것.

## 처리 완료

| # | 심각도 | 이슈 | 처리 | 브랜치/커밋 |
|---|---|---|---|---|
| 1 | 심각 | 로그아웃이 refresh token을 revoke하지 않음 + 쿠키 삭제 path 불일치 | 수정 | `fix/auth-security` f489ef9 |
| 2 | 심각 | Rate limiter 미적용 (로그인 brute-force, 인증코드 폭탄 무방비) | 수정 — login/register/password-reset/인증코드 엔드포인트에 slowapi 적용 | `fix/auth-security` f489ef9 |
| 3 | 심각 | MySQL naive datetime vs aware 비교 → `/auth/refresh`, 인증코드 검증에서 TypeError | 수정 — `app/core/timeutils.py` `as_utc()` 헬퍼 도입 | `fix/auth-security` 73ffd77 |
| 4 | 심각 | 거래완료(판매된) 매물이 `active`로 수집되어 시세 통계 오염. daangn 1,706건 확인 | 수정 — 배지 파싱 → `sold` 저장, 기존 데이터 backfill 완료 | `fix/crawler-sold-status` |

## 미처리 (우선순위순)

### 심각

| # | 이슈 | 위치 | 비고 |
|---|---|---|---|
| 5 | admin 크롤러 수동 트리거가 닫힌 request-scoped DB 세션을 백그라운드 태스크에 전달 → 실패. 태스크 참조도 미보관(GC 위험) | `endpoints/admin.py:154` | admin 페이지 스펙 P0. `AsyncSessionLocal()`로 새 세션 생성 필요 |
| 6 | OAuth `state` 파라미터 없음 (CSRF 취약) | `endpoints/auth.py` oauth redirect/callback | |
| 7 | `SECRET_KEY` 기본값("change-me-in-production")으로 배포 가능 — JWT 위조 위험 | `core/config.py:35` | 프로덕션에서 기본값이면 기동 실패하는 validator 추가 |

### 높음

| # | 이슈 | 위치 | 비고 |
|---|---|---|---|
| 8 | 동기 smtplib가 이벤트 루프 블로킹 — 메일 발송 동안 서버 전체 정지 | `services/notification.py:23` | `asyncio.to_thread` 또는 aiosmtplib(이미 requirements에 있음) |
| 9 | 회원가입 race condition — check-then-insert, IntegrityError 시 500 | `services/auth.py:21` | catch 후 409 변환 |
| 10 | Kakao OAuth 이메일/닉네임 fallback 충돌 시 500 | `endpoints/auth.py:161` | unique 제약 위반 처리 |
| 11 | 탈퇴 계정 복구 불가능 (죽은 엔드포인트) — 탈퇴 유저는 로그인/토큰 획득 자체가 차단됨 | `auth.py:195`, `dependencies.py:25` | 복구 플로우 재설계 필요 |
| 12 | `item`에 `(source, external_id)` unique 제약 없음 — 크롤러 동시 실행 시 중복 insert 가능 | `db/models/item.py` | 마이그레이션 필요 |
| 13 | 크롤링에서 사라진 매물이 영구 `active`로 잔류 (stale 매물) | `crawlers/base.py` | "N일 이상 미재수집 시 stale 처리" 정책 필요. #4와 별개 문제 |

### 중간

| # | 이슈 | 위치 | 비고 |
|---|---|---|---|
| 14 | 자동완성이 SKU 전체 풀스캔 + Python 필터링 | `endpoints/search.py:32` | SKU 증가 시 성능 병목 1순위 |
| 15 | N+1 쿼리 다수 | `items.py:78`, `alert.py:46`, `crawlers/base.py:110` | |
| 16 | 스케줄러 잡에 `max_instances`/`misfire_grace_time` 미설정 | `core/scheduler.py:40` | 크롤링 겹침/유실 정책 명시 필요 |
| 17 | 스케줄 문자열 파싱 검증 없음 — 형식 오류 시 앱 기동 실패 | `core/scheduler.py:37` | |
| 18 | Playwright 크롤러가 API 프로세스 내 실행 — 메모리/지연 리스크 | 구조 | EC2 배포 시 인스턴스 사이징 고려 (t3.medium 권장) |
| 19 | 토큰 재사용 감지 로직에 결과를 버리는 중복 쿼리 | `core/dependencies.py:58` | |

### 사소

| # | 이슈 | 위치 |
|---|---|---|
| 20 | `items_upserted`가 신규 insert만 카운트 (갱신 미포함) — 지표 왜곡 | `crawlers/base.py` |
| 21 | `admin/stats`의 `active_today` 항상 0 (TODO 방치) | `endpoints/admin.py:88` |
| 22 | oauth_redirect의 무의미한 `response.headers.update(...) or` 표현 | `endpoints/auth.py:115` |
| 23 | `updated_at` onupdate가 naive `datetime.utcnow` — 시각 처리 표준 불일치 | `db/models/*.py` |

## 결정 기록 (Decisions)

| 날짜 | 결정 | 근거 |
|---|---|---|
| 2026-07-05 | 브랜치 전략: `main`(안정) / `dev`(통합) / feature 브랜치 → dev PR | 단일 브랜치 운영에서 전환 |
| 2026-07-05 | admin 페이지 스펙 확정 — `docs/admin-page-spec.md` | 크롤러 모니터링을 1급 가치로 |
| 2026-07-07 | 거래완료 매물은 삭제 대신 `status=sold` 저장 | item_id 참조(알림 등) 보존, 판매 이력 데이터로 활용 가능 |
| 2026-07-07 | "예약중" 매물은 `active` 유지 (배지만 제거) | 아직 거래 미완료로 시세에 유효 |
| 2026-07-07 | 번개장터 API `status != "0"`은 sold 처리 | 판매중="0" 확인됨, 그 외 값은 보수적으로 제외 |

## 인프라 메모

- 로컬 MySQL: docker `howmuch-mysql-3307` (포트 **3307**, docker-compose 기본값 3306과 다름 주의)
- 백엔드 실행 환경: `backend/.venv` (python3.12), `backend/.env`에 DB 접속 정보
- 크롤러 수동 실행: `cd backend && .venv/bin/python -m app.crawlers.run --platform daangn --limit-targets 1 --limit-items 5`
- EC2 배포 시: Playwright chromium 메모리 때문에 t3.small+스왑 또는 t3.medium 권장, NAT Gateway 사용 금지 (비용)
