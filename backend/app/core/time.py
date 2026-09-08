"""시각 처리 유틸 — 저장·비교는 전부 UTC로 통일한다.

배경: MySQL DATETIME은 타임존을 저장하지 않는다. 컬럼을 DateTime(timezone=True)로
선언해도 asyncmy는 naive datetime을 돌려주므로, aware 값과 그냥 비교하면
"can't compare offset-naive and offset-aware datetimes"로 터진다.
실제로 RefreshToken.is_valid와 Verification.is_expired가 이 문제로 항상 500을
반환해 토큰 갱신과 인증 코드 확인이 동작하지 않았다.

규칙:
- 애플리케이션이 쓰는 시각은 utc_now()로 만든다 (aware UTC)
- DB에서 읽은 값을 비교할 때는 as_utc()로 감싼다
- 컬럼 기본값(NOW())은 DB 세션 타임존이 UTC라는 전제에 의존한다
  (session.py가 커넥션마다 SET time_zone='+00:00'을 걸고, compose도
  --default-time-zone=+00:00을 준다)
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """현재 시각 (aware UTC)."""
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """DB에서 읽은 naive datetime을 UTC로 간주해 aware로 만든다.

    이미 aware면 그대로 둔다. 저장은 전부 UTC 기준이므로 naive 값을 UTC로
    해석하면 맞다.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def as_utc_or_none(value: datetime | None) -> datetime | None:
    """None을 허용하는 as_utc."""
    return None if value is None else as_utc(value)
