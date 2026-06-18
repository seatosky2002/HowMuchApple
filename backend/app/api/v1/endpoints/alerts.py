from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.alert import (
    AlertListResponse,
    BulkDeleteRequest,
    BulkDeleteResponse,
    UnreadCountResponse,
)
from app.schemas.common import MessageResponse
from app.services import alert as alert_service

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    is_read: bool | None = Query(default=None),
    watch_id: int | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await alert_service.list_alerts(db, current_user, is_read, watch_id, from_date, page, page_size)
    from app.schemas.alert import AlertDetail, AlertItemDetail
    alerts = []
    for a in data["alerts"]:
        item = AlertItemDetail(**a["item"]) if a.get("item") else None
        alerts.append(AlertDetail(
            alert_id=a["alert_id"],
            watch_id=a["watch_id"],
            watch_label=a.get("watch_label"),
            spec_label=a.get("spec_label", ""),
            message=a["message"],
            item=item,
            is_read=a["is_read"],
            triggered_at=a["triggered_at"],
        ))
    return AlertListResponse(total=data["total"], unread=data["unread"], alerts=alerts)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    count = await alert_service.unread_count(db, current_user)
    return UnreadCountResponse(unread=count)


@router.patch("/{alert_id}/read", response_model=MessageResponse)
async def mark_read(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await alert_service.mark_read(db, current_user, alert_id)
    return MessageResponse(message="읽음 처리되었습니다.")


@router.patch("/read-all", response_model=MessageResponse)
async def mark_all_read(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await alert_service.mark_all_read(db, current_user)
    return MessageResponse(message="전체 읽음 처리되었습니다.")


@router.delete("/{alert_id}", response_model=MessageResponse)
async def delete_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await alert_service.delete_alert(db, current_user, alert_id)
    return MessageResponse(message="알림이 삭제되었습니다.")


@router.delete("", response_model=BulkDeleteResponse)
async def bulk_delete_alerts(
    body: BulkDeleteRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ids = body.alert_ids if body else None
    deleted = await alert_service.bulk_delete_alerts(db, current_user, ids)
    return BulkDeleteResponse(deleted_count=deleted)
