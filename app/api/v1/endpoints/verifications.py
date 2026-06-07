from fastapi import APIRouter, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import MessageResponse
from app.schemas.verification import (
    EmailVerificationRequest,
    EmailVerifyRequest,
    PhoneVerificationRequest,
    PhoneVerifyRequest,
    VerifiedResponse,
)
from app.services import verification as verification_service

router = APIRouter(prefix="/verifications", tags=["Verifications"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/email", response_model=MessageResponse)
async def send_email_code(
    body: EmailVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verification_service.send_email_code(db, current_user)
    return MessageResponse(message="인증번호를 발송했습니다. 5분 내 입력해주세요.")


@router.post("/email/verify", response_model=VerifiedResponse)
async def verify_email(
    body: EmailVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    verified = await verification_service.verify_email_code(db, current_user, body.email, body.code)
    return VerifiedResponse(verified=verified)


@router.post("/phone", response_model=MessageResponse)
async def send_phone_code(
    body: PhoneVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verification_service.send_phone_code(db, current_user, body.phone)
    return MessageResponse(message="인증번호를 발송했습니다.")


@router.post("/phone/verify", response_model=VerifiedResponse)
async def verify_phone(
    body: PhoneVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    verified = await verification_service.verify_phone_code(db, current_user, body.phone, body.code)
    return VerifiedResponse(verified=verified)
