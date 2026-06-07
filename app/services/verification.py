from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest
from app.core.security import create_verification_code, verify_code
from app.db.models.user import User, Verification, VerificationType
from app.services.notification import send_sms, send_verification_email

VERIFICATION_EXPIRE_MINUTES = 5


async def send_email_code(db: AsyncSession, user: User) -> None:
    code, hashed = create_verification_code()
    verification = Verification(
        user_id=user.user_id,
        type=VerificationType.email,
        target=user.email,
        code_hash=hashed,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=VERIFICATION_EXPIRE_MINUTES),
    )
    db.add(verification)
    await db.commit()
    await send_verification_email(user.email, code)


async def verify_email_code(db: AsyncSession, user: User, email: str, code: str) -> bool:
    if user.email != email:
        raise BadRequest("이메일이 일치하지 않습니다.")

    result = await db.execute(
        select(Verification)
        .where(
            Verification.user_id == user.user_id,
            Verification.type == VerificationType.email,
            Verification.target == email,
            Verification.verified_at.is_(None),
        )
        .order_by(Verification.created_at.desc())
    )
    record = result.scalars().first()

    if not record or record.is_expired:
        raise BadRequest("인증번호가 만료되었거나 존재하지 않습니다.")
    if not verify_code(code, record.code_hash):
        raise BadRequest("인증번호가 올바르지 않습니다.")

    record.verified_at = datetime.now(timezone.utc)
    user.is_email_verified = True
    await db.commit()
    return True


async def send_phone_code(db: AsyncSession, user: User, phone: str) -> None:
    code, hashed = create_verification_code()
    verification = Verification(
        user_id=user.user_id,
        type=VerificationType.phone,
        target=phone,
        code_hash=hashed,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=VERIFICATION_EXPIRE_MINUTES),
    )
    db.add(verification)
    await db.commit()
    await send_sms(phone, f"[HowMuch] 인증번호: {code}")


async def verify_phone_code(db: AsyncSession, user: User, phone: str, code: str) -> bool:
    result = await db.execute(
        select(Verification)
        .where(
            Verification.user_id == user.user_id,
            Verification.type == VerificationType.phone,
            Verification.target == phone,
            Verification.verified_at.is_(None),
        )
        .order_by(Verification.created_at.desc())
    )
    record = result.scalars().first()

    if not record or record.is_expired:
        raise BadRequest("인증번호가 만료되었거나 존재하지 않습니다.")
    if not verify_code(code, record.code_hash):
        raise BadRequest("인증번호가 올바르지 않습니다.")

    record.verified_at = datetime.now(timezone.utc)
    user.phone = phone
    user.is_phone_verified = True
    await db.commit()
    return True
