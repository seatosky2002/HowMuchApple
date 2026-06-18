from datetime import timedelta

import httpx
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_refresh_token_record
from app.core.exceptions import BadRequest
from app.db.models.user import RefreshToken, User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    OAuthCallbackResponse,
    PasswordResetConfirmBody,
    PasswordResetRequestBody,
    RegisterRequest,
    RegisterResponse,
)
from app.schemas.common import MessageResponse, OkResponse
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])

_COOKIE_OPTS = dict(
    httponly=True,
    samesite=settings.COOKIE_SAMESITE,
    secure=settings.COOKIE_SECURE,
    domain=settings.COOKIE_DOMAIN or None,
)


def _set_tokens(response: Response, access: str, refresh: str) -> None:
    response.set_cookie("access_token", access, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/", **_COOKIE_OPTS)
    response.set_cookie(
        "refresh_token",
        refresh,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth/refresh",
        **_COOKIE_OPTS,
    )


def _clear_tokens(response: Response) -> None:
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await auth_service.register(db, body.email, body.password, body.nickname)
    access, refresh = await auth_service.issue_tokens(db, user)
    _set_tokens(response, access, refresh)
    return RegisterResponse(
        user_id=user.user_id,
        email=user.email,
        nickname=user.nickname,
        is_verified=user.is_email_verified,
    )


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await auth_service.login(db, body.email, body.password)
    access, refresh = await auth_service.issue_tokens(db, user)
    _set_tokens(response, access, refresh)
    return LoginResponse(user_id=user.user_id, nickname=user.nickname)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    refresh_token: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from fastapi import Cookie as FastAPICookie
    _clear_tokens(response)
    return MessageResponse(message="logged out")


@router.post("/refresh", response_model=OkResponse)
async def refresh(
    response: Response,
    token_data: tuple[RefreshToken, AsyncSession] = Depends(get_refresh_token_record),
):
    record, db = token_data
    access, new_refresh = await auth_service.rotate_refresh_token(db, record)
    _set_tokens(response, access, new_refresh)
    return OkResponse()


@router.post("/password-reset/request", response_model=MessageResponse)
async def password_reset_request(body: PasswordResetRequestBody, db: AsyncSession = Depends(get_db)):
    await auth_service.request_password_reset(db, body.email)
    return MessageResponse(message="이메일이 존재하면 인증 메일을 발송했습니다.")


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def password_reset_confirm(body: PasswordResetConfirmBody, db: AsyncSession = Depends(get_db)):
    await auth_service.confirm_password_reset(db, body.token, body.new_password)
    return MessageResponse(message="비밀번호가 변경되었습니다.")


@router.get("/oauth/{provider}/redirect")
async def oauth_redirect(provider: str, response: Response):
    if provider == "kakao":
        url = (
            f"https://kauth.kakao.com/oauth/authorize"
            f"?client_id={settings.KAKAO_CLIENT_ID}"
            f"&redirect_uri={settings.KAKAO_REDIRECT_URI}"
            f"&response_type=code"
        )
        return response.headers.update({"Location": url}) or Response(status_code=302, headers={"Location": url})
    elif provider == "apple":
        url = (
            f"https://appleid.apple.com/auth/authorize"
            f"?client_id={settings.APPLE_CLIENT_ID}"
            f"&redirect_uri={settings.APPLE_REDIRECT_URI}"
            f"&response_type=code id_token"
            f"&scope=name email"
            f"&response_mode=form_post"
        )
        return Response(status_code=302, headers={"Location": url})
    raise BadRequest("지원하지 않는 OAuth 제공자입니다.")


@router.get("/oauth/{provider}/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(
    provider: str,
    code: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    if provider == "kakao":
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://kauth.kakao.com/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.KAKAO_CLIENT_ID,
                    "client_secret": settings.KAKAO_CLIENT_SECRET,
                    "redirect_uri": settings.KAKAO_REDIRECT_URI,
                    "code": code,
                },
            )
            token_data = token_res.json()
            kakao_access = token_data.get("access_token")
            if not kakao_access:
                raise BadRequest("카카오 인증에 실패했습니다.")

            profile_res = await client.get(
                "https://kapi.kakao.com/v2/user/me",
                headers={"Authorization": f"Bearer {kakao_access}"},
            )
            profile = profile_res.json()

        kakao_id = str(profile.get("id"))
        kakao_account = profile.get("kakao_account", {})
        email = kakao_account.get("email", f"{kakao_id}@kakao.com")
        nickname = profile.get("properties", {}).get("nickname", f"카카오_{kakao_id[:6]}")

        from sqlalchemy import select
        from app.db.models.user import User as UserModel

        result = await db.execute(
            select(UserModel).where(UserModel.oauth_provider == "kakao", UserModel.oauth_subject == kakao_id)
        )
        user = result.scalar_one_or_none()
        is_new = user is None

        if not user:
            from app.core.security import hash_password
            import secrets
            user = UserModel(
                email=email,
                nickname=nickname,
                password_hash=None,
                oauth_provider="kakao",
                oauth_subject=kakao_id,
                is_email_verified=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        access, refresh = await auth_service.issue_tokens(db, user)
        _set_tokens(response, access, refresh)
        return OAuthCallbackResponse(user_id=user.user_id, nickname=user.nickname, is_new=is_new)

    raise BadRequest("지원하지 않는 OAuth 제공자입니다.")


@router.post("/account/restore", response_model=MessageResponse)
async def restore_account(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await auth_service.restore_account(db, current_user.user_id)
    return MessageResponse(message="계정이 복구되었습니다.")
