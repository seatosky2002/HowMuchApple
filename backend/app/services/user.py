from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, Conflict
from app.core.security import hash_password, verify_password
from app.db.models.user import User
from app.schemas.user import (
    AlertChannels,
    DndSettings,
    NotificationSettings,
    NotificationSettingsUpdate,
    UserMeResponse,
    UserUpdateRequest,
)


async def get_me(user: User) -> UserMeResponse:
    phone_masked = None
    if user.phone:
        p = user.phone.replace("-", "")
        phone_masked = f"{p[:3]}-****-{p[-4:]}"

    return UserMeResponse(
        user_id=user.user_id,
        email=user.email,
        nickname=user.nickname,
        is_verified=user.is_email_verified,
        alert_channels=AlertChannels(email=user.alert_email, sms=user.alert_sms),
        phone=phone_masked,
        created_at=user.created_at,
    )


async def update_me(db: AsyncSession, user: User, data: UserUpdateRequest) -> User:
    if data.nickname and data.nickname != user.nickname:
        existing = await db.execute(select(User).where(User.nickname == data.nickname))
        if existing.scalar_one_or_none():
            raise Conflict("이미 사용 중인 닉네임입니다.")
        user.nickname = data.nickname

    await db.commit()
    await db.refresh(user)
    return user


async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    if not user.password_hash:
        raise BadRequest("소셜 로그인 계정은 비밀번호를 변경할 수 없습니다.")
    if not verify_password(current_password, user.password_hash):
        raise BadRequest("현재 비밀번호가 올바르지 않습니다.")
    user.password_hash = hash_password(new_password)
    await db.commit()


async def soft_delete(db: AsyncSession, user: User) -> None:
    user.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def check_email(db: AsyncSession, email: str) -> bool:
    result = await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))
    return result.scalar_one_or_none() is None


async def check_nickname(db: AsyncSession, nickname: str) -> bool:
    result = await db.execute(select(User).where(User.nickname == nickname, User.deleted_at.is_(None)))
    return result.scalar_one_or_none() is None


async def get_notification_settings(user: User) -> NotificationSettings:
    return NotificationSettings(
        channels=AlertChannels(email=user.alert_email, sms=user.alert_sms),
        dnd=DndSettings(enabled=user.dnd_enabled, start=user.dnd_start, end=user.dnd_end),
        watchlist_alerts_enabled=user.watchlist_alerts_enabled,
    )


async def update_notification_settings(
    db: AsyncSession, user: User, data: NotificationSettingsUpdate
) -> NotificationSettings:
    if data.channels is not None:
        user.alert_email = data.channels.email
        user.alert_sms = data.channels.sms
    if data.dnd is not None:
        user.dnd_enabled = data.dnd.enabled
        user.dnd_start = data.dnd.start
        user.dnd_end = data.dnd.end
    if data.watchlist_alerts_enabled is not None:
        user.watchlist_alerts_enabled = data.watchlist_alerts_enabled

    await db.commit()
    return await get_notification_settings(user)
