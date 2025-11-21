from typing import List, Optional, Dict
from pydantic import BaseModel, Field, validator


class Choice(BaseModel):
    target: str
    text: Optional[str] = None


class Combat(BaseModel):
    skill: int
    stamina: int
    name: Optional[str] = None


class ItemEffect(BaseModel):
    description: Optional[str] = None
    delta_gold: Optional[int] = None
    delta_provisions: Optional[int] = None
    add_item: Optional[str] = None
    use_item: Optional[str] = None

    @validator("description", always=True)
    def default_desc(cls, v, values):
        if v:
            return v
        parts = []
        for key in ("delta_gold", "delta_provisions", "add_item", "use_item"):
            if values.get(key) is not None:
                parts.append(f"{key}:{values.get(key)}")
        if parts:
            return "; ".join(parts)
        return "effect"


class Paragraph(BaseModel):
    id: str
    page: int = 0
    text: str
    choices: List[Choice] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    combat: Optional[Combat] = None
    test_luck: Optional[bool] = None
    item_effects: List[ItemEffect] = Field(default_factory=list)

    @validator("id")
    def id_is_numeric(cls, v):
        if not v.isdigit():
            raise ValueError("id must be numeric string")
        return v

    @validator("item_effects", pre=True, always=True)
    def item_effects_default(cls, v):
        if v is None:
            return []
        if isinstance(v, dict):
            return [v]
        return v


class PageResult(BaseModel):
    paragraphs: List[Paragraph]


class PortionHypothesis(BaseModel):
    portion_id: Optional[str] = None
    page_start: int
    page_end: int
    title: Optional[str] = None
    type: Optional[str] = None
    confidence: float = 0.5
    notes: Optional[str] = None
    source_window: List[int] = Field(default_factory=list)
    source_pages: List[int] = Field(default_factory=list)
    continuation_of: Optional[str] = None
    continuation_confidence: Optional[float] = None


class LockedPortion(BaseModel):
    portion_id: str
    page_start: int
    page_end: int
    title: Optional[str] = None
    type: Optional[str] = None
    confidence: float
    source_images: List[str] = Field(default_factory=list)
