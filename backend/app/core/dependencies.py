from datetime import datetime, timezone

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Forbidden, Unauthorized
from app.core.security import decode_access_token, hash_token
from app.db.models.user import RefreshToken, User, UserStatus
from app.db.session import get_db


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not access_token:
        raise Unauthorized("로그인이 필요합니다.")

    user_id = decode_access_token(access_token)
    if not user_id:
        raise Unauthorized("유효하지 않은 토큰입니다.")

    user = await db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise Unauthorized("존재하지 않는 사용자입니다.")
    if user.status == UserStatus.suspended:
        raise Forbidden("정지된 계정입니다.")

    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise Forbidden("관리자 권한이 필요합니다.")
    return current_user


async def get_refresh_token_record(
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> tuple[RefreshToken, AsyncSession]:
    if not refresh_token:
        raise Unauthorized("refresh_token이 없습니다.")

    hashed = hash_token(refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == hashed))
    record = result.scalar_one_or_none()

    if not record:
        raise Unauthorized("유효하지 않은 refresh_token입니다.")

    if not record.is_valid:
        if record.revoked_at is not None:
            # Token reuse detected — revoke all sessions
            await db.execute(
                select(RefreshToken)
                .where(RefreshToken.user_id == record.user_id, RefreshToken.revoked_at.is_(None))
            )
            all_tokens = (
                await db.execute(
                    select(RefreshToken).where(
                        RefreshToken.user_id == record.user_id,
                        RefreshToken.revoked_at.is_(None),
                    )
                )
            ).scalars().all()
            for t in all_tokens:
                t.revoked_at = datetime.now(timezone.utc)
            await db.commit()
        raise Unauthorized("만료되었거나 취소된 refresh_token입니다.")

    return record, db
