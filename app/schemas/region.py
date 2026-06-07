from pydantic import BaseModel


class SDItem(BaseModel):
    sd_id: int
    name: str
    model_config = {"from_attributes": True}


class SGGItem(BaseModel):
    sgg_id: int
    name: str
    model_config = {"from_attributes": True}


class EMDItem(BaseModel):
    region_id: int
    name: str
    model_config = {"from_attributes": True}


class SDListResponse(BaseModel):
    regions: list[SDItem]


class SGGListResponse(BaseModel):
    sgg: list[SGGItem]


class EMDListResponse(BaseModel):
    emd: list[EMDItem]
