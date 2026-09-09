"""장애 알림 발송 — Discord/Slack Incoming Webhook.

기존 send_email()은 SMTP 자격증명이 없으면 로그만 찍는 스텁이고 운영 .env에도
설정이 없다. send_sms()는 provider 미결이다. 그래서 설정이 URL 하나뿐인 Webhook을
1차 채널로 쓴다 (docs/MONITORING_PLAN.md 5절).

URL이 비어 있으면 로그만 남기고 조용히 통과한다 — 알림 실패가 크롤이나 API를
망가뜨리면 안 된다.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT_S = 10


def _payload(url: str, text: str) -> dict:
    """Discord와 Slack의 본문 키가 다르다. URL로 판별한다.

    설정 항목을 하나 더 두는 대신 URL을 보고 정하면 사용자가 채널을 바꿀 때
    URL만 갈아끼우면 된다.
    """
    if "hooks.slack.com" in url:
        return {"text": text}
    # Discord (discord.com/api/webhooks/...) 및 호환 엔드포인트
    return {"content": text}


async def send_webhook(text: str) -> bool:
    """알림을 발송한다. 성공 여부를 돌려주지만 예외는 던지지 않는다."""
    url = settings.ALERT_WEBHOOK_URL
    if not url:
        logger.info("[WEBHOOK STUB] ALERT_WEBHOOK_URL 미설정 — 내용:\n%s", text)
        return False

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(url, json=_payload(url, text))
        if resp.status_code >= 300:
            logger.error("웹훅 발송 실패: HTTP %s %s", resp.status_code, resp.text[:200])
            return False
        return True
    except Exception as e:
        # 알림이 실패해도 호출한 배치는 계속 돌아야 한다
        logger.error("웹훅 발송 예외: %s", e)
        return False
