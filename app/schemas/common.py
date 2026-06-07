from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class OkResponse(BaseModel):
    ok: bool = True
