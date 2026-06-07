from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    nickname: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다.")
        return v

    @field_validator("nickname")
    @classmethod
    def nickname_length(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("닉네임은 2자 이상이어야 합니다.")
        return v.strip()


class RegisterResponse(BaseModel):
    user_id: int
    email: str
    nickname: str
    is_verified: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user_id: int
    nickname: str


class PasswordResetRequestBody(BaseModel):
    email: EmailStr


class PasswordResetConfirmBody(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다.")
        return v


class OAuthCallbackResponse(BaseModel):
    user_id: int
    nickname: str
    is_new: bool
