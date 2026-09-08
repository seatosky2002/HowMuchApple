from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "HowMuch API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DB: str = "howmuch"
    MYSQL_USER: str = "howmuch"
    MYSQL_PASSWORD: str = ""
    MYSQL_CHARSET: str = "utf8mb4"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+asyncmy://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            f"?charset={self.MYSQL_CHARSET}"
        )

    @property
    def SYNC_DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            f"?charset={self.MYSQL_CHARSET}"
        )

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    COOKIE_DOMAIN: str = ""
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "strict"

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""
    FROM_NAME: str = "HowMuch"

    KAKAO_CLIENT_ID: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    KAKAO_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/kakao/callback"

    APPLE_CLIENT_ID: str = ""
    APPLE_TEAM_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_PRIVATE_KEY: str = ""
    APPLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/apple/callback"

    FRONTEND_URL: str = "http://localhost:3000"

    CRAWLER_SCHEDULE: str = "0 6 * * *"
    ALERT_SCHEDULE: str = "30 6 * * *"

    # 크롤 감시 임계값 — /api/v1/health/crawlers 판정에 쓴다.
    # 크롤이 하루 한 번(CRAWLER_SCHEDULE) 도므로 24시간 + 여유 2시간.
    CRAWLER_STALE_HOURS: int = 26
    # 세 플랫폼 합계가 약 1시간 40분이라 4시간을 넘겨 running이면 멈춘 것으로 본다
    # (실제로 수동 실행이 SSH 종료로 끊겨 running이 영구 잔류한 사례가 있다).
    CRAWLER_RUNNING_MAX_HOURS: int = 4

    # 감시 알림 (docs/MONITORING_PLAN.md). Discord/Slack Incoming Webhook URL.
    # 비어 있으면 알림을 로그로만 남긴다.
    ALERT_WEBHOOK_URL: str = ""
    # 같은 장애가 이어질 때 재알림까지 기다리는 시간 (알림 피로 방지)
    ALERT_SUPPRESS_HOURS: int = 24
    # 크롤이 아예 시작조차 못 한 경우를 잡는 일일 재점검 (크롤 종료 이후 시각)
    MONITOR_SCHEDULE: str = "0 8 * * *"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
