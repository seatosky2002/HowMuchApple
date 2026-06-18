import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequest, Conflict, Unauthorized
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.models.user import RefreshToken, User, Verification, VerificationType, UserStatus
from app.services.notification import send_password_reset_email


async def register(db: AsyncSession, email: str, password: str, nickname: str) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise Conflict("이미 사용 중인 이메일입니다.")

    nick_check = await db.execute(select(User).where(User.nickname == nickname))
    if nick_check.scalar_one_or_none():
        raise Conflict("이미 사용 중인 닉네임입니다.")

    user = User(
        email=email,
        password_hash=hash_password(password),
        nickname=nickname,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise Unauthorized("이메일 또는 비밀번호가 올바르지 않습니다.")
    if not verify_password(password, user.password_hash):
        raise Unauthorized("이메일 또는 비밀번호가 올바르지 않습니다.")
    if user.deleted_at is not None:
        raise Unauthorized("탈퇴한 계정입니다. 복구를 원하시면 재로그인 후 복구 요청을 해주세요.")
    if user.status == UserStatus.suspended:
        raise Unauthorized("정지된 계정입니다.")

    return user


async def issue_tokens(db: AsyncSession, user: User) -> tuple[str, str]:
    access = create_access_token(user.user_id)
    raw_refresh, hashed_refresh = create_refresh_token()

    token = RefreshToken(
        user_id=user.user_id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(token)
    await db.commit()
    return access, raw_refresh


async def rotate_refresh_token(db: AsyncSession, old_record: RefreshToken) -> tuple[str, str]:
    old_record.revoked_at = datetime.now(timezone.utc)

    access = create_access_token(old_record.user_id)
    raw_refresh, hashed_refresh = create_refresh_token()

    new_token = RefreshToken(
        user_id=old_record.user_id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_token)
    await db.commit()
    return access, raw_refresh


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    hashed = hash_token(raw_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == hashed))
    record = result.scalar_one_or_none()
    if record and record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
        await db.commit()


async def request_password_reset(db: AsyncSession, email: str) -> None:
    result = await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if not user:
        return  # 이메일 존재 여부 노출 금지

    token = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(token.encode()).hexdigest()

    verification = Verification(
        user_id=user.user_id,
        type=VerificationType.password_reset,
        target=email,
        code_hash=hashed,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(verification)
    await db.commit()

    await send_password_reset_email(email, token, settings.FRONTEND_URL)


async def confirm_password_reset(db: AsyncSession, token: str, new_password: str) -> None:
    hashed = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(Verification).where(
            Verification.code_hash == hashed,
            Verification.type == VerificationType.password_reset,
            Verification.verified_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()

    if not record or record.is_expired:
        raise BadRequest("유효하지 않거나 만료된 토큰입니다.")

    user = await db.get(User, record.user_id)
    if not user:
        raise BadRequest("사용자를 찾을 수 없습니다.")

    user.password_hash = hash_password(new_password)
    record.verified_at = datetime.now(timezone.utc)
    await db.commit()


async def restore_account(db: AsyncSession, user_id: int) -> None:
    user = await db.get(User, user_id)
    if not user or user.deleted_at is None:
        raise BadRequest("복구할 계정이 없습니다.")

    diff = datetime.now(timezone.utc) - user.deleted_at.replace(tzinfo=timezone.utc)
    if diff.days > 30:
        raise BadRequest("복구 가능 기간(30일)이 지났습니다.")

    user.deleted_at = None
    await db.commit()
