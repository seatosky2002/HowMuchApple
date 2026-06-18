import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body: str) -> bool:
    if not settings.SMTP_USER:
        logger.info("[EMAIL STUB] to=%s subject=%s", to, subject)
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>"
        msg["To"] = to
        msg.attach(MIMEText(body, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.FROM_EMAIL, to, msg.as_string())
        return True
    except Exception as e:
        logger.error("이메일 발송 실패: %s", e)
        return False


async def send_sms(to: str, message: str) -> bool:
    # SMS provider 미결 사항 — 현재 로깅만
    logger.info("[SMS STUB] to=%s message=%s", to, message)
    return True


async def send_verification_email(email: str, code: str) -> bool:
    subject = "[HowMuch] 이메일 인증번호"
    body = f"""
    <p>안녕하세요!</p>
    <p>이메일 인증번호: <strong>{code}</strong></p>
    <p>5분 이내에 입력해주세요.</p>
    """
    return await send_email(email, subject, body)


async def send_password_reset_email(email: str, token: str, frontend_url: str) -> bool:
    link = f"{frontend_url}/reset-password?token={token}"
    subject = "[HowMuch] 비밀번호 재설정"
    body = f"""
    <p>아래 링크를 클릭하여 비밀번호를 재설정하세요:</p>
    <a href="{link}">{link}</a>
    <p>링크는 1시간 후 만료됩니다.</p>
    """
    return await send_email(email, subject, body)


async def send_alert_email(email: str, message: str, source_url: str) -> bool:
    subject = "[HowMuch] 가격 알림"
    body = f"""
    <p>{message}</p>
    <p><a href="{source_url}">매물 보러가기</a></p>
    """
    return await send_email(email, subject, body)
