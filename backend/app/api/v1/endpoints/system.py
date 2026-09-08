from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["System"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    from app.core.scheduler import scheduler
    scheduler_status = "ok" if scheduler.running else "error"

    overall = "ok" if db_status == "ok" and scheduler_status == "ok" else "degraded"

    response = {
        "status": overall,
        "db": db_status,
        "scheduler": scheduler_status,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=response,
        status_code=200 if overall == "ok" else 503,
    )


@router.get("/health/crawlers")
async def crawler_health(db: AsyncSession = Depends(get_db)):
    """크롤 신선도를 인증 없이 판정한다 — 외부 감시(GitHub Actions cron)용.

    /health는 db·scheduler만 보고 크롤이 며칠 멈춰도 ok를 반환한다. 판정 로직은
    app/services/crawler_monitor.py 한 곳에 있고 서버 내부 알림 잡도 같은 것을
    쓴다(두 곳에 복사하면 반드시 어긋난다).

    상태가 ok가 아니면 503을 반환하므로 감시 쪽은 `curl -f` 한 줄로 끝난다.
    """
    from fastapi.responses import JSONResponse

    from app.services.crawler_monitor import evaluate_crawler_health

    health = await evaluate_crawler_health(db)
    return JSONResponse(
        content={**health.to_dict(), "checked_at": datetime.now(timezone.utc).isoformat()},
        status_code=200 if health.is_ok else 503,
    )
