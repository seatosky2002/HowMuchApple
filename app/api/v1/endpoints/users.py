from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import MessageResponse
from app.schemas.user import (
    AvailableResponse,
    CheckEmailRequest,
    CheckNicknameRequest,
    NotificationSettings,
    NotificationSettingsUpdate,
    PasswordChangeRequest,
    UserMeResponse,
    UserUpdateRequest,
)
from app.services import user as user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserMeResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return await user_service.get_me(current_user)


@router.patch("/me", response_model=UserMeResponse)
async def update_me(
    body: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.update_me(db, current_user, body)
    return await user_service.get_me(user)


@router.patch("/me/password", response_model=MessageResponse)
async def change_password(
    body: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await user_service.change_password(db, current_user, body.current_password, body.new_password)
    return MessageResponse(message="비밀번호가 변경되었습니다.")


@router.delete("/me", response_model=MessageResponse)
async def delete_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await user_service.soft_delete(db, current_user)
    return MessageResponse(message="탈퇴 처리되었습니다. 30일 이내 재로그인 시 복구 가능합니다.")


@router.post("/check-email", response_model=AvailableResponse)
async def check_email(body: CheckEmailRequest, db: AsyncSession = Depends(get_db)):
    available = await user_service.check_email(db, body.email)
    return AvailableResponse(available=available)


@router.post("/check-nickname", response_model=AvailableResponse)
async def check_nickname(body: CheckNicknameRequest, db: AsyncSession = Depends(get_db)):
    available = await user_service.check_nickname(db, body.nickname)
    return AvailableResponse(available=available)


@router.get("/me/notification-settings", response_model=NotificationSettings)
async def get_notification_settings(current_user: User = Depends(get_current_user)):
    return await user_service.get_notification_settings(current_user)


@router.patch("/me/notification-settings", response_model=NotificationSettings)
async def update_notification_settings(
    body: NotificationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.update_notification_settings(db, current_user, body)
