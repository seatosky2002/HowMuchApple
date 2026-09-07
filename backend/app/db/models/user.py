import enum
from datetime import datetime, time, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, Time, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _as_utc(value: datetime) -> datetime:
    """MySQL에서 읽어온 naive datetime을 UTC로 간주해 aware로 만든다.

    컬럼은 DateTime(timezone=True)이지만 MySQL DATETIME은 타임존을 저장하지 않아
    asyncmy가 naive로 돌려준다. 그대로 datetime.now(timezone.utc)와 비교하면
    "can't compare offset-naive and offset-aware datetimes"로 터진다.
    저장은 전부 datetime.now(timezone.utc) 기준이라 naive 값은 UTC로 해석하면 맞다.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class UserStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class VerificationType(str, enum.Enum):
    email = "email"
    phone = "phone"
    password_reset = "password_reset"


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_email: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_sms: Mapped[bool] = mapped_column(Boolean, default=False)
    dnd_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    dnd_start: Mapped[time | None] = mapped_column(Time)
    dnd_end: Mapped[time | None] = mapped_column(Time)
    watchlist_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.active)
    oauth_provider: Mapped[str | None] = mapped_column(String(20))
    oauth_subject: Mapped[str | None] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), onupdate=datetime.utcnow
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    verifications: Mapped[list["Verification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    watchlists: Mapped[list["Watchlist"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    token_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    @property
    def is_valid(self) -> bool:
        return self.revoked_at is None and _as_utc(self.expires_at) > datetime.now(timezone.utc)


class Verification(Base):
    __tablename__ = "verification"

    verification_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    type: Mapped[VerificationType] = mapped_column(Enum(VerificationType), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    user: Mapped["User"] = relationship(back_populates="verifications")

    @property
    def is_expired(self) -> bool:
        return _as_utc(self.expires_at) < datetime.now(timezone.utc)
