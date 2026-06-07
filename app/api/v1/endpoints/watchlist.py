from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import MessageResponse
from app.schemas.watchlist import (
    ActiveToggleResponse,
    WatchlistAlertsResponse,
    WatchlistCreateRequest,
    WatchlistDetailResponse,
    WatchlistResponse,
    WatchlistUpdateRequest,
)
from app.services import watchlist as watchlist_service

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


@router.get("", response_model=WatchlistResponse)
async def list_watchlist(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    items = await watchlist_service.list_watchlist(db, current_user)
    from app.schemas.watchlist import WatchlistItem
    return WatchlistResponse(watchlist=[WatchlistItem(**i) for i in items])


@router.post("", status_code=201)
async def create_watchlist(
    body: WatchlistCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    w = await watchlist_service.create_watchlist(db, current_user, body)
    channels = []
    if w.alert_email:
        channels.append("email")
    if w.alert_sms:
        channels.append("sms")
    return {
        "watch_id": w.watch_id,
        "sku_id": w.sku_id,
        "label": w.label,
        "region_id": w.region_id,
        "max_price": w.max_price,
        "is_active": w.is_active,
        "alert_channels": channels,
        "created_at": w.created_at,
    }


@router.get("/{watch_id}", response_model=WatchlistDetailResponse)
async def get_watchlist(
    watch_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await watchlist_service.get_watchlist(db, current_user, watch_id)
    return WatchlistDetailResponse(**data)


@router.patch("/{watch_id}")
async def update_watchlist(
    watch_id: int,
    body: WatchlistUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    w = await watchlist_service.update_watchlist(db, current_user, watch_id, body)
    return {"watch_id": w.watch_id, "max_price": w.max_price, "label": w.label}


@router.patch("/{watch_id}/active", response_model=ActiveToggleResponse)
async def toggle_active(
    watch_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    w = await watchlist_service.toggle_active(db, current_user, watch_id)
    return ActiveToggleResponse(watch_id=w.watch_id, is_active=w.is_active)


@router.delete("/{watch_id}", response_model=MessageResponse)
async def delete_watchlist(
    watch_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await watchlist_service.delete_watchlist(db, current_user, watch_id)
    return MessageResponse(message="찜이 삭제되었습니다.")


@router.get("/{watch_id}/alerts", response_model=WatchlistAlertsResponse)
async def get_watchlist_alerts(
    watch_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await watchlist_service.get_watchlist_alerts(db, current_user, watch_id, page, page_size)
    return WatchlistAlertsResponse(**data)
