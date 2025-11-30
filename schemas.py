from typing import Any, Dict, List, Optional, Literal, Union
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
    raw_text: Optional[str] = None  # Text extracted from elements/pages
    element_ids: Optional[List[str]] = None  # Source element IDs for provenance


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
    raw_text: Optional[str] = None  # Text extracted from elements/pages
    element_ids: Optional[List[str]] = None  # Source element IDs for provenance


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
    raw_text: Optional[str] = None  # Text extracted from elements/pages
    element_ids: Optional[List[str]] = None  # Source element IDs for provenance


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
    element_ids: Optional[List[str]] = None  # Source element IDs for provenance


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


# ────────────────────────────────────────────────────────────────
# Document IR – Unstructured-native element representation
# ────────────────────────────────────────────────────────────────


class CodexMetadata(BaseModel):
    """
    Codex-forge metadata namespace for provenance and internal tracking.

    This is added to each Unstructured element to track our pipeline metadata
    without polluting the Unstructured fields.

    Note: This is serialized as '_codex' in JSON (see UnstructuredElement.model_dump).
    """
    run_id: Optional[str] = None
    module_id: Optional[str] = None
    sequence: Optional[int] = None  # Order within document (for stable sorting)
    created_at: Optional[str] = None


class UnstructuredElement(BaseModel):
    """
    Wrapper for Unstructured element serialized to JSON.

    This is the core Document IR format for codex-forge. We preserve Unstructured's
    native element structure (type, text, metadata) and add a 'codex' namespace
    for our provenance tracking.

    Unstructured provides rich element types:
    - Title, NarrativeText, Text, ListItem, Table, Image
    - Header, Footer, FigureCaption, PageBreak, etc.

    We preserve these exactly as Unstructured provides them, keeping all metadata:
    - metadata.page_number (1-based)
    - metadata.coordinates (bbox points)
    - metadata.text_as_html (for tables)
    - metadata.parent_id (hierarchy)
    - metadata.emphasized_text_contents, emphasized_text_tags
    - metadata.detection_class_prob (confidence scores)
    - ... and any other fields Unstructured provides

    This approach:
    - Keeps the IR rich and future-proof as Unstructured evolves
    - Avoids normalization complexity
    - Preserves all provenance and layout information
    - Makes downstream code simpler (one source of truth)

    Note: When serializing to JSON, use model_dump(by_alias=True) to get '_codex'
    instead of 'codex' in the output.
    """
    # Core Unstructured fields
    id: str  # Element ID from Unstructured or generated UUID
    type: str  # Unstructured element type (Title, NarrativeText, Table, etc.)
    text: str = ""  # Plain text content

    # Unstructured metadata (preserve all fields as-is)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Codex-forge namespace for our tracking (aliased to '_codex' in JSON)
    codex: CodexMetadata = Field(default_factory=CodexMetadata, alias="_codex")

    class Config:
        # Allow extra fields for forward compatibility
        extra = "allow"
        # Support both 'codex' and '_codex' when parsing
        populate_by_name = True


# ────────────────────────────────────────────────────────────────
# Fighting Fantasy AI Pipeline Schemas
# ────────────────────────────────────────────────────────────────


class SectionBoundary(BaseModel):
    """
    AI-detected section boundary in Fighting Fantasy book.

    This schema represents a single gameplay section detected by AI analysis.
    The AI scans elements to find section numbers (1-400) and identifies the
    start/end element IDs that bound each section's content.
    """
    schema_version: str = "section_boundary_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None

    section_id: str  # "1", "2", "3", etc. (Fighting Fantasy section numbers)
    start_element_id: str  # ID of first element in this section
    end_element_id: Optional[str] = None  # ID of last element (None if extends to next section)
    confidence: float  # 0.0-1.0, AI's confidence this is a real section boundary
    evidence: Optional[str] = None  # Why AI thinks this is a section boundary


class BoundaryIssue(BaseModel):
    """Single boundary issue discovered during verification."""
    section_id: str
    severity: Literal["error", "warning"]
    message: str
    start_element_id: Optional[str] = None
    page: Optional[int] = None
    evidence: Optional[str] = None


class BoundaryVerificationReport(BaseModel):
    """Report produced by verify_boundaries_v1."""
    schema_version: str = "boundary_verification_v1"
    run_id: Optional[str] = None
    checked: int
    errors: List[BoundaryIssue] = Field(default_factory=list)
    warnings: List[BoundaryIssue] = Field(default_factory=list)
    ai_samples: List[Dict[str, Any]] = Field(default_factory=list)
    is_valid: bool = True


class ValidationReport(BaseModel):
    """
    Validation report for Fighting Fantasy Engine output.

    This schema captures quality checks on the final gamebook.json output,
    including missing sections, duplicates, and structural issues.
    """
    schema_version: str = "validation_report_v1"
    run_id: Optional[str] = None
    created_at: Optional[str] = None

    total_sections: int
    missing_sections: List[str] = Field(default_factory=list)  # Section IDs that should exist but don't
    duplicate_sections: List[str] = Field(default_factory=list)  # Section IDs appearing multiple times
    sections_with_no_text: List[str] = Field(default_factory=list)
    sections_with_no_choices: List[str] = Field(default_factory=list)

    is_valid: bool  # True if no critical errors
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


# ────────────────────────────────────────────────────────────────
# Pipeline Redesign v2: Minimal IR Schemas
# ────────────────────────────────────────────────────────────────


class ElementLayout(BaseModel):
    """Layout information for an element (simplified from Unstructured metadata)."""
    h_align: str = "unknown"  # "left" | "center" | "right" | "unknown"
    y: Optional[float] = None  # Normalized vertical position 0-1 on page


class ElementCore(BaseModel):
    """
    Minimal internal IR schema for all AI operations.
    
    This schema reduces Unstructured's verbose IR to only the essential fields
    needed for section detection and boundary identification. All subsequent
    AI work depends only on elements_core.jsonl plus derived artifacts.
    
    Per pipeline redesign spec: {id, seq, page, kind, text, layout}
    No metadata fields (schema_version, module_id, run_id, created_at) to minimize
    AI workload and improve readability. Metadata lives in pipeline state/manifests.
    
    Derived from UnstructuredElement by:
    - Preserving id, text, page
    - Adding seq (0-based reading order index, preserved from original)
    - Mapping Unstructured types to simple "kind" categories
    - Extracting layout hints (alignment, vertical position)
    - Filtering out empty elements (text.strip() == "")
    """
    id: str  # Original element ID from Unstructured
    seq: int  # Global reading-order index (0-based, preserved from original elements_full)
    page: int  # Page number as reported by Unstructured (1-based)
    kind: str  # "text" | "image" | "table" | "other"
    text: str  # Raw text, normalized whitespace only (non-empty after filtering)
    layout: Optional[ElementLayout] = None  # Layout hints if available


class HeaderCandidate(BaseModel):
    """
    AI-classified header candidate from element-level analysis.
    
    This schema represents the output of Stage 1 (Header Classification), where AI
    analyzes each element to identify if it's a macro section header or game section header.
    This stage labels candidates only - it does not decide final section mapping.
    
    Per pipeline redesign spec v2: header_candidates.jsonl contains all elements with
    their classification results, not just positives, for downstream context.
    """
    seq: int  # Element sequence number (from elements_core)
    page: int  # Page number (from elements_core)
    macro_header: str = "none"  # "none" | "cover" | "title_page" | "rules" | "introduction" | ...
    game_section_header: bool = False  # True if this is a numbered gameplay section header
    claimed_section_number: Optional[int] = None  # Section number (1-400) if game_section_header is true
    confidence: float  # 0.0-1.0, AI's confidence in this classification
    text: Optional[str] = None  # Text content from elements_core (for verification)


class MacroSection(BaseModel):
    """Macro section (front_matter, game_sections region, etc.)"""
    id: str  # "front_matter", "game_sections", etc.
    start_seq: int  # Starting sequence number
    end_seq: int  # Ending sequence number
    confidence: float  # 0.0-1.0


class GameSectionStructured(BaseModel):
    """Game section with structured metadata from global analysis"""
    id: int  # Section number (1-400)
    start_seq: Optional[int] = None  # Starting sequence number (null if uncertain)
    status: Literal["certain", "uncertain"] = "certain"  # Status of this section
    confidence: float  # 0.0-1.0
    text: Optional[str] = None  # Full text content from start_seq until next section (for verification)
    text_length: Optional[int] = None  # Length of text in characters


class SectionsStructured(BaseModel):
    """
    Global structured view of document sections from Stage 2.
    
    This schema represents the output of Stage 2 (Global Structuring), where a single
    AI call analyzes header candidates to create a coherent global structure with
    macro sections and game sections.
    
    Per pipeline redesign spec v2: sections_structured.json contains macro sections
    (front_matter, game_sections) and game sections with strict ordering constraints.
    """
    macro_sections: List[MacroSection]  # Macro sections (front_matter, game_sections region)
    game_sections: List[GameSectionStructured]  # Game sections with status (certain/uncertain)
