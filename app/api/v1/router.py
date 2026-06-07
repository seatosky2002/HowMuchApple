from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    alerts,
    analytics,
    auth,
    categories,
    items,
    regions,
    search,
    sku,
    stats,
    system,
    users,
    verifications,
    watchlist,
)

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(verifications.router)
router.include_router(categories.router)
router.include_router(regions.router)
router.include_router(sku.router)
router.include_router(analytics.router)
router.include_router(items.router)
router.include_router(watchlist.router)
router.include_router(alerts.router)
router.include_router(search.router)
router.include_router(stats.router)
router.include_router(admin.router)
router.include_router(system.router)
