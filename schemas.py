from typing import List, Optional, Dict
from pydantic import BaseModel, Field, field_validator, model_validator


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

    @model_validator(mode="after")
    def default_desc(self):
        if self.description:
            return self
        parts = []
        for key in ("delta_gold", "delta_provisions", "add_item", "use_item"):
            val = getattr(self, key)
            if val is not None:
                parts.append(f"{key}:{val}")
        self.description = "; ".join(parts) if parts else "effect"
        return self


class Paragraph(BaseModel):
    id: str
    page: int = 0
    text: str
    choices: List[Choice] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    combat: Optional[Combat] = None
    test_luck: Optional[bool] = None
    item_effects: List[ItemEffect] = Field(default_factory=list)

    @field_validator("id")
    def id_is_numeric(cls, v):
        if not v.isdigit():
            raise ValueError("id must be numeric string")
        return v

    @field_validator("item_effects", mode="before")
    def item_effects_default(cls, v):
        if v is None:
            return []
        if isinstance(v, dict):
            return [v]
        return v


class PageResult(BaseModel):
    paragraphs: List[Paragraph]


class PageDoc(BaseModel):
    schema_version: str = "page_doc_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
    page: int
    image: Optional[str] = None
    text: str
    source_path: Optional[str] = None


class CleanPage(BaseModel):
    schema_version: str = "clean_page_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
    page: int
    image: Optional[str] = None
    raw_text: str
    clean_text: str
    confidence: float


class PortionHypothesis(BaseModel):
    schema_version: str = "portion_hyp_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
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
    schema_version: str = "locked_portion_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
    portion_id: str
    page_start: int
    page_end: int
    title: Optional[str] = None
    type: Optional[str] = None
    confidence: float
    source_images: List[str] = Field(default_factory=list)


class ResolvedPortion(BaseModel):
    schema_version: str = "resolved_portion_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
    portion_id: str
    page_start: int
    page_end: int
    title: Optional[str] = None
    type: Optional[str] = None
    confidence: float = 0.0
    source_images: List[str] = Field(default_factory=list)
    orig_portion_id: Optional[str] = None


class EnrichedPortion(BaseModel):
    schema_version: str = "enriched_portion_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
    portion_id: str
    section_id: Optional[str] = None
    page_start: int
    page_end: int
    title: Optional[str] = None
    type: Optional[str] = None
    confidence: float = 0.0
    source_images: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None
    choices: List[Choice] = Field(default_factory=list)
    combat: Optional[Combat] = None
    test_luck: Optional[bool] = None
    item_effects: List[ItemEffect] = Field(default_factory=list)
    targets: List[str] = Field(default_factory=list)
