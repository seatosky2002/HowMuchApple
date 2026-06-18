from pydantic import BaseModel, EmailStr


class EmailVerificationRequest(BaseModel):
    email: EmailStr


class EmailVerifyRequest(BaseModel):
    email: EmailStr
    code: str


class PhoneVerificationRequest(BaseModel):
    phone: str


class PhoneVerifyRequest(BaseModel):
    phone: str
    code: str


class VerifiedResponse(BaseModel):
    verified: bool
