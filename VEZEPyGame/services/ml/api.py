from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import math

router = APIRouter()


class SkillReq(BaseModel):
    features: list[float]


class SkillRes(BaseModel):
    skill: float


@router.post("/predict_skill", response_model=SkillRes)
def predict_skill(r: SkillReq):
    if not r.features:
        raise HTTPException(400, "features required")
    # Dev stub: compute a normalized score
    s = sum(max(0.0, x) for x in r.features) / (len(r.features) or 1)
    return SkillRes(skill=float(s))


class BotReq(BaseModel):
    signals: list[float]


class BotRes(BaseModel):
    is_bot: bool
    score: float


@router.post("/detect_bot", response_model=BotRes)
def detect_bot(r: BotReq):
    score = float(min(1.0, max(0.0, (sum(r.signals) / (len(r.signals) or 1)) / 100.0)))
    return BotRes(is_bot=score > 0.7, score=score)
