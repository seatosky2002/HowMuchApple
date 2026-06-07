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
