from typing import Any, Dict, List, Optional, Literal
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


class BoundingBox(BaseModel):
    x0: int
    y0: int
    x1: int
    y1: int
    section_id: Optional[str] = None


class ImageCrop(BaseModel):
    schema_version: str = "image_crop_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
    page: int
    image: str
    boxes: List[BoundingBox]
    crops: List[str]


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
    continuation_of: Optional[str] = None
    continuation_confidence: Optional[float] = None


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
    continuation_of: Optional[str] = None
    continuation_confidence: Optional[float] = None


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
    continuation_of: Optional[str] = None
    continuation_confidence: Optional[float] = None
    choices: List[Choice] = Field(default_factory=list)
    combat: Optional[Combat] = None
    test_luck: Optional[bool] = None
    item_effects: List[ItemEffect] = Field(default_factory=list)
    targets: List[str] = Field(default_factory=list)


class LLMCallUsage(BaseModel):
    schema_version: str = "instrumentation_call_v1"
    model: str
    provider: str = "openai"
    prompt_tokens: int
    completion_tokens: int
    cached: bool = False
    request_ms: Optional[float] = None
    request_id: Optional[str] = None
    cost: Optional[float] = None
    stage_id: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None

    @field_validator("prompt_tokens", "completion_tokens")
    def non_negative_tokens(cls, v):
        if v < 0:
            raise ValueError("token counts must be non-negative")
        return v

    @field_validator("request_ms")
    def non_negative_latency(cls, v):
        if v is not None and v < 0:
            raise ValueError("request_ms must be non-negative")
        return v


class StageInstrumentation(BaseModel):
    schema_version: str = "instrumentation_stage_v1"
    id: str
    stage: str
    module_id: Optional[str] = None
    status: str
    artifact: Optional[str] = None
    schema_version_output: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    wall_seconds: Optional[float] = None
    cpu_user_seconds: Optional[float] = None
    cpu_system_seconds: Optional[float] = None
    llm_calls: List[LLMCallUsage] = Field(default_factory=list)
    llm_totals: Dict[str, Any] = Field(default_factory=dict)
    extra: Dict[str, Any] = Field(default_factory=dict)


class RunInstrumentation(BaseModel):
    schema_version: str = "instrumentation_run_v1"
    run_id: str
    recipe_name: Optional[str] = None
    recipe_path: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    wall_seconds: Optional[float] = None
    cpu_user_seconds: Optional[float] = None
    cpu_system_seconds: Optional[float] = None
    stages: List[StageInstrumentation] = Field(default_factory=list)
    totals: Dict[str, Any] = Field(default_factory=dict)
    pricing: Dict[str, Any] = Field(default_factory=dict)
    env: Dict[str, Any] = Field(default_factory=dict)


class ContactSheetBBox(BaseModel):
    x: int
    y: int
    width: int
    height: int

    @model_validator(mode="after")
    def positive_dims(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        return self


class ContactSheetTile(BaseModel):
    schema_version: str = "contact_sheet_manifest_v1"
    sheet_id: str
    tile_index: int = Field(ge=0)
    source_image: str
    display_number: int = Field(ge=0)
    sheet_path: str
    tile_bbox: Optional[ContactSheetBBox] = None
    orig_size: Optional[Dict[str, int]] = None  # {"width": int, "height": int}


class PageSpan(BaseModel):
    start_image: str
    end_image: str


class SectionPlan(BaseModel):
    label: str
    type: str
    page_spans: List[PageSpan] = Field(default_factory=list)
    notes: Optional[str] = None


class CapabilityGap(BaseModel):
    capability: str
    severity: Literal["missing", "partial"] = "missing"
    suggested_action: Optional[str] = None
    notes: Optional[str] = None
    pages: List[str] = Field(default_factory=list)


class SignalEvidence(BaseModel):
    signal: str
    pages: List[str] = Field(default_factory=list)
    reason: Optional[str] = None


class IntakePlan(BaseModel):
    schema_version: str = "intake_plan_v1"
    book_type: Literal[
        "novel",
        "cyoa",
        "genealogy",
        "textbook",
        "mixed",
        "other",
    ]
    type_confidence: Optional[float] = None
    sections: List[SectionPlan] = Field(default_factory=list)
    zoom_requests: List[str] = Field(default_factory=list)
    recommended_recipe: Optional[str] = None
    sectioning_strategy: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    signals: List[str] = Field(default_factory=list)
    sheets: List[str] = Field(default_factory=list)
    manifest_path: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    capability_gaps: List[CapabilityGap] = Field(default_factory=list)
    recommended_recipe: Optional[str] = None
    signal_evidence: List[SignalEvidence] = Field(default_factory=list)

    @field_validator("type_confidence")
    def confidence_range(cls, v):
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("type_confidence must be between 0 and 1")
        return v
