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

    # cron 형식 (분 시 일 월 요일), Asia/Seoul 기준
    CRAWLER_SCHEDULE: str = "0 6,15 * * *"  # 매일 06:00, 15:00
    ALERT_SCHEDULE: str = "30 7,16 * * *"  # 크롤링 시작 1.5시간 후 (전체 크롤링 ~1시간 여유)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
