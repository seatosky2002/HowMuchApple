from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.region import EMD, SD, SGG
from app.db.session import get_db
from app.schemas.region import EMDItem, EMDListResponse, SDItem, SDListResponse, SGGItem, SGGListResponse

router = APIRouter(prefix="/regions", tags=["Regions"])


@router.get("", response_model=SDListResponse)
async def list_sd(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SD).order_by(SD.sd_id))
    return SDListResponse(regions=[SDItem.model_validate(r) for r in result.scalars().all()])


@router.get("/{sd_id}/sgg", response_model=SGGListResponse)
async def list_sgg(sd_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SGG).where(SGG.sd_id == sd_id).order_by(SGG.sgg_id))
    return SGGListResponse(sgg=[SGGItem.model_validate(s) for s in result.scalars().all()])


@router.get("/{sgg_id}/emd", response_model=EMDListResponse)
async def list_emd(sgg_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EMD).where(EMD.sgg_id == sgg_id).order_by(EMD.region_id))
    return EMDListResponse(emd=[EMDItem.model_validate(e) for e in result.scalars().all()])
