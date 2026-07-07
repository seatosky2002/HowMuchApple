from datetime import datetime, timezone


def as_utc(value: datetime) -> datetime:
    """naive datetime을 UTC로 간주해 aware로 변환.

    MySQL DATETIME은 타임존을 저장하지 않아 조회 시 naive로 반환된다.
    이 프로젝트는 모든 시각을 UTC로 저장하므로 UTC를 붙여 비교 가능하게 만든다.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
