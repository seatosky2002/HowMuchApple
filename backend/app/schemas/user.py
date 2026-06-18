from datetime import datetime, time

from pydantic import BaseModel, EmailStr, field_validator


class AlertChannels(BaseModel):
    email: bool
    sms: bool


class UserMeResponse(BaseModel):
    user_id: int
    email: str
    nickname: str
    is_verified: bool
    alert_channels: AlertChannels
    phone: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    nickname: str | None = None

    @field_validator("nickname")
    @classmethod
    def nickname_length(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) < 2:
            raise ValueError("닉네임은 2자 이상이어야 합니다.")
        return v.strip() if v else v


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다.")
        return v


class CheckEmailRequest(BaseModel):
    email: EmailStr


class CheckNicknameRequest(BaseModel):
    nickname: str


class AvailableResponse(BaseModel):
    available: bool


class NotificationSettings(BaseModel):
    channels: AlertChannels
    dnd: "DndSettings"
    watchlist_alerts_enabled: bool

    model_config = {"from_attributes": True}


class DndSettings(BaseModel):
    enabled: bool
    start: time | None
    end: time | None


class NotificationSettingsUpdate(BaseModel):
    channels: AlertChannels | None = None
    dnd: DndSettings | None = None
    watchlist_alerts_enabled: bool | None = None
