from fastapi import APIRouter
from pydantic import BaseModel
import re

router = APIRouter()

_bg_color = {"value": "#ffffff"}

_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class BgColorRequest(BaseModel):
    color: str


@router.get("/bg-color")
def get_bg_color():
    return {"color": _bg_color["value"]}


@router.put("/bg-color")
def set_bg_color(body: BgColorRequest):
    if not _HEX_RE.match(body.color):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Неверный формат цвета. Ожидается HEX (#fff или #ffffff)")
    _bg_color["value"] = body.color
    return {"color": _bg_color["value"]}
