from typing import Any, Dict, List, Optional, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class Choice(BaseModel):
    target: str
    text: Optional[str] = None


class CombatEnemy(BaseModel):
    enemy: Optional[str] = None
    skill: Optional[int] = None
    stamina: Optional[int] = None
    armour: Optional[int] = None
    firepower: Optional[int] = None
    speed: Optional[str] = None


class Combat(BaseModel):
    enemies: List[CombatEnemy] = Field(default_factory=list)
    outcomes: Optional[Dict[str, Any]] = None
    mode: Optional[str] = None
    style: Optional[str] = None
    rules: Optional[List[Dict[str, Any]]] = None
    modifiers: Optional[List[Dict[str, Any]]] = None
    triggers: Optional[List[Dict[str, Any]]] = None
    confidence: float = 1.0


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


class InventoryItem(BaseModel):
    item: str
    quantity: Union[int, str] = 1
    confidence: float = 1.0


class InventoryState(BaseModel):
    action: Literal["lose_all", "restore_all"]
    scope: str = "possessions"
    confidence: float = 1.0


class StateValue(BaseModel):
    key: str
    value: str
    confidence: float = 1.0
    source_text: Optional[str] = None


class StateCheck(BaseModel):
    key: Optional[str] = None
    condition_text: Optional[str] = None
    template_target: Optional[str] = None
    template_op: Optional[str] = None
    template_value: Optional[str] = None
    choice_text: Optional[str] = None
    has_target: Optional[str] = None
    missing_target: Optional[str] = None
    confidence: float = 1.0


class InventoryCheck(BaseModel):
    item: str
    condition: str = "if you have"  # "if you have", "if you possess", etc.
    target_section: Optional[str] = None
    confidence: float = 1.0


class InventoryEnrichment(BaseModel):
    items_gained: List[InventoryItem] = Field(default_factory=list)
    items_lost: List[InventoryItem] = Field(default_factory=list)
    items_used: List[InventoryItem] = Field(default_factory=list)
    inventory_checks: List[InventoryCheck] = Field(default_factory=list)
    inventory_states: List[InventoryState] = Field(default_factory=list)


class StatCheck(BaseModel):
    stat: Optional[Union[str, List[str]]] = None  # SKILL, LUCK, STAMINA, or list
    dice_roll: str = "2d6"
    dice_count: int = 2
    dice_sides: int = 6
    pass_condition: str = "success"  # e.g., "total <= stat" or "1-3"
    pass_section: str
    fail_condition: Optional[str] = None
    fail_section: Optional[str] = None
    confidence: float = 1.0


class TestLuck(BaseModel):
    lucky_section: str
    unlucky_section: str
    confidence: float = 1.0


class StatModification(BaseModel):
    stat: str  # skill, stamina, luck (lowercase normalized)
    amount: Union[int, str]
    scope: str = "section"
    reason: Optional[str] = None
    confidence: float = 1.0


class Paragraph(BaseModel):
    id: str
    page: int = 0
    text: str
    choices: List[Choice] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    combat: List[Combat] = Field(default_factory=list)
    test_luck: List[TestLuck] = Field(default_factory=list)
    stat_checks: List[StatCheck] = Field(default_factory=list)
    stat_modifications: List[StatModification] = Field(default_factory=list)
    item_effects: List[ItemEffect] = Field(default_factory=list)
    inventory: Optional[InventoryEnrichment] = None

    @field_validator("id")
    def id_is_numeric(cls, v):
        if not v.isdigit():
            raise ValueError("id must be numeric string")
        return v

    @field_validator("combat", mode="before")
    def combat_default(cls, v):
        if v is None:
            return []
        if isinstance(v, dict):
            return [v]
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
    page_number: Optional[int] = None
    original_page_number: Optional[int] = None
    image: Optional[str] = None
    text: str
    source_path: Optional[str] = None


class PageImage(BaseModel):
    schema_version: str = "page_image_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
    page: int
    page_number: Optional[int] = None
    original_page_number: Optional[int] = None
    image: str
    spread_side: Optional[str] = None


class PageHtml(BaseModel):
    schema_version: str = "page_html_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
    page: int
    page_number: Optional[int] = None
    original_page_number: Optional[int] = None
    image: Optional[str] = None
    spread_side: Optional[str] = None
    # OCR diagnostics (optional; populated by AI OCR stage)
    ocr_quality: Optional[float] = None
    ocr_integrity: Optional[float] = None
    continuation_risk: Optional[float] = None
    ocr_metadata_warning: Optional[str] = None
    ocr_metadata_tag: Optional[str] = None
    ocr_metadata_missing: Optional[bool] = None
    ocr_empty: Optional[bool] = None
    ocr_empty_reason: Optional[str] = None
    raw_html: Optional[str] = None
    html: str


class HtmlBlock(BaseModel):
    block_type: str
    text: str
    order: int
    attrs: Optional[Dict[str, Any]] = None
    element_id: Optional[str] = None


class PageHtmlBlocks(BaseModel):
    schema_version: str = "page_html_blocks_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
    page: int
    page_number: Optional[int] = None
    original_page_number: Optional[int] = None
    image: Optional[str] = None
    spread_side: Optional[str] = None
    is_blank: bool = False
    blocks: List[HtmlBlock] = Field(default_factory=list)


class PipelineIssues(BaseModel):
    schema_version: str = "pipeline_issues_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None
    summary: Dict[str, Any]
    issues: List[Dict[str, Any]]


class EdgecaseScanReport(BaseModel):
    schema_version: str = "edgecase_scan_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None
    summary: Dict[str, Any]
    issues: List[Dict[str, Any]]


class EdgecasePatchRecord(BaseModel):
    schema_version: str = "edgecase_patch_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None
    section_id: str
    reason_code: str
    path: str
    op: str
    value: Optional[Any] = None
    ai_rationale: Optional[str] = None


class EdgecasePatchReport(BaseModel):
    schema_version: str = "edgecase_patch_report_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None
    summary: Dict[str, Any]
    patches: List[Dict[str, Any]]


class TurnToLinksRecord(BaseModel):
    schema_version: str = "turn_to_links_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None
    section_id: str
    portion_id: Optional[str] = None
    pageStart: Optional[int] = None
    pageEnd: Optional[int] = None
    links: List[Dict[str, Any]]


class TurnToLinkClaim(BaseModel):
    schema_version: str = "turn_to_link_claims_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None
    section_id: str
    portion_id: Optional[str] = None
    target: str
    claim_type: str
    evidence_path: Optional[str] = None


class TurnToLinkClaimInline(BaseModel):
    target: str
    claim_type: str
    module_id: Optional[str] = None
    evidence_path: Optional[str] = None


class TurnToUnclaimedReport(BaseModel):
    schema_version: str = "turn_to_unclaimed_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None
    summary: Dict[str, Any]
    issues: List[Dict[str, Any]]


class PageLine(BaseModel):
    text: str
    source: Optional[str] = None  # e.g., "betterocr", "gpt4v", "llm_reconcile"
    meta: Optional[Dict[str, Any]] = None  # engine-level details, confidences, alignment notes
    bbox: Optional[List[float]] = None  # Optional normalized bbox [x0,y0,x1,y1] when available (0-1)


class PageLines(BaseModel):
    schema_version: str = "pagelines_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
    page: int
    page_number: Optional[int] = None
    original_page_number: Optional[int] = None
    image: Optional[str] = None
    lines: List[PageLine]
    disagreement_score: Optional[float] = None
    needs_escalation: bool = False
    # Optional provenance/quality fields (kept during driver stamping).
    # Many OCR modules emit these, and downstream adapters/guards rely on them.
    engines_raw: Optional[Dict[str, Any]] = None
    quality_metrics: Optional[Dict[str, Any]] = None
    column_spans: Optional[List[List[float]]] = None
    column_confidence: Optional[Dict[str, Any]] = None
    ivr: Optional[float] = None
    inline_escalated: Optional[bool] = None
    spread_side: Optional[str] = None  # "L", "R", or None
    meta: Optional[Dict[str, Any]] = None
    escalation_reasons: Optional[List[str]] = None


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
    page_number: Optional[int] = None
    original_page_number: Optional[int] = None
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
    page_number: Optional[int] = None
    original_page_number: Optional[int] = None
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
    page_start_original: Optional[int] = None
    page_end_original: Optional[int] = None
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
    macro_section: Optional[str] = None  # frontmatter | gameplay | endmatter


class LockedPortion(BaseModel):
    schema_version: str = "locked_portion_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
    portion_id: str
    page_start: int
    page_end: int
    page_start_original: Optional[int] = None
    page_end_original: Optional[int] = None
    title: Optional[str] = None
    type: Optional[str] = None
    confidence: float
    source_images: List[str] = Field(default_factory=list)
    continuation_of: Optional[str] = None
    continuation_confidence: Optional[float] = None
    raw_text: Optional[str] = None  # Text extracted from elements/pages
    element_ids: Optional[List[str]] = None  # Source element IDs for provenance
    macro_section: Optional[str] = None  # frontmatter | gameplay | endmatter


class ResolvedPortion(BaseModel):
    schema_version: str = "resolved_portion_v1"
    module_id: Optional[str] = None
    run_id: Optional[str] = None
    source: Optional[List[str]] = None
    created_at: Optional[str] = None
    portion_id: str
    page_start: int
    page_end: int
    page_start_original: Optional[int] = None
    page_end_original: Optional[int] = None
    title: Optional[str] = None
    type: Optional[str] = None
    confidence: float = 0.0
    source_images: List[str] = Field(default_factory=list)
    orig_portion_id: Optional[str] = None
    continuation_of: Optional[str] = None
    continuation_confidence: Optional[float] = None
    raw_text: Optional[str] = None  # Text extracted from elements/pages
    element_ids: Optional[List[str]] = None  # Source element IDs for provenance
    macro_section: Optional[str] = None  # frontmatter | gameplay | endmatter


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
    page_start_original: Optional[int] = None
    page_end_original: Optional[int] = None
    title: Optional[str] = None
    type: Optional[str] = None
    confidence: float = 0.0
    source_images: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None
    raw_text_original: Optional[str] = None
    clean_text: Optional[str] = None
    raw_html: Optional[str] = None
    continuation_of: Optional[str] = None
    continuation_confidence: Optional[float] = None
    choices: List[Choice] = Field(default_factory=list)
    combat: List[Combat] = Field(default_factory=list)
    test_luck: List[TestLuck] = Field(default_factory=list)
    stat_checks: List[StatCheck] = Field(default_factory=list)
    stat_modifications: List[StatModification] = Field(default_factory=list)
    item_effects: List[ItemEffect] = Field(default_factory=list)
    inventory: Optional[InventoryEnrichment] = None
    state_values: List[StateValue] = Field(default_factory=list)
    state_checks: List[StateCheck] = Field(default_factory=list)
    targets: List[str] = Field(default_factory=list)
    turn_to_links: List[str] = Field(default_factory=list)
    turn_to_claims: List[TurnToLinkClaimInline] = Field(default_factory=list)
    element_ids: Optional[List[str]] = None  # Source element IDs for provenance
    repair: Optional[Dict[str, Any]] = None
    repair_hints: Optional[Dict[str, Any]] = None
    context_correction: Optional[Dict[str, Any]] = None
    macro_section: Optional[str] = None  # frontmatter | gameplay | endmatter
    is_gameplay: Optional[bool] = None
    end_game: Optional[bool] = None
    ending: Optional[str] = None
    sequence: Optional[List[Dict[str, Any]]] = None

    @field_validator("combat", mode="before")
    def combat_default(cls, v):
        if v is None:
            return []
        if isinstance(v, dict):
            return [v]
        return v


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
    # Optional provenance helpers (code-first + vision escalation modules may emit these)
    start_page: Optional[int] = None
    start_line_idx: Optional[int] = None
    end_page: Optional[int] = None
    macro_section: Optional[str] = None  # frontmatter | gameplay | endmatter
    method: Optional[str] = None  # "code_filter" | "vision_escalation" | ...
    source: Optional[str] = None  # "content_type_classification" | "escalation_cache" | ...
    header_position: Optional[str] = None  # "top" | "middle" | "bottom" | "unknown"
    confidence: float  # 0.0-1.0, AI's confidence this is a real section boundary
    evidence: Optional[str] = None  # Why AI thinks this is a section boundary

    class Config:
        extra = "allow"


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
    
    Note: Reachability analysis (unreachable_sections) is performed by the
    canonical Node validator (validate_ff_engine_node_v1) and merged into
    this report for consistency.
    """
    schema_version: str = "validation_report_v1"
    run_id: Optional[str] = None
    created_at: Optional[str] = None

    total_sections: int
    missing_sections: List[str] = Field(default_factory=list)  # Section IDs that should exist but don't
    duplicate_sections: List[str] = Field(default_factory=list)  # Section IDs appearing multiple times
    sections_with_no_text: List[str] = Field(default_factory=list)
    sections_with_no_choices: List[str] = Field(default_factory=list)
    unreachable_sections: List[str] = Field(default_factory=list)  # Sections unreachable from startSection (from Node validator)

    is_valid: bool  # True if no critical errors
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    forensics: Optional[Dict[str, Any]] = None


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
    page_number: Optional[int] = None
    original_page_number: Optional[int] = None
    kind: str  # "text" | "image" | "table" | "other"
    text: str  # Raw text, normalized whitespace only (non-empty after filtering)
    layout: Optional[ElementLayout] = None  # Layout hints if available
    layout_role: Optional[str] = None  # Optional upstream-provided role hint (e.g., TITLE, HEADER, FOOTER)
    content_type: Optional[str] = None  # DocLayNet label (or compatible), when available
    content_type_confidence: Optional[float] = None  # 0.0-1.0
    content_subtype: Optional[Dict[str, Any]] = None  # Small optional subtype payload (e.g., heading_level)


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


# ────────────────────────────────────────────────────────────────
# Run Configuration Schemas
# ────────────────────────────────────────────────────────────────


class ExecutionConfig(BaseModel):
    start_from: Optional[str] = None
    end_at: Optional[str] = None
    skip_done: bool = False
    force: bool = False
    dry_run: bool = False


class OptionsConfig(BaseModel):
    mock: bool = False
    no_validate: bool = False
    allow_run_id_reuse: bool = False
    dump_plan: bool = False


class InstrumentationConfig(BaseModel):
    enabled: bool = False
    price_table: Optional[str] = None


class RunConfig(BaseModel):
    """
    Structured configuration for a pipeline run.
    Captures all parameters previously passed as CLI arguments to driver.py.
    """
    run_id: Optional[str] = None
    recipe: str
    registry: str = "modules"
    settings: Optional[str] = None
    input_pdf: Optional[str] = None
    output_dir: Optional[str] = None
    
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    options: OptionsConfig = Field(default_factory=OptionsConfig)
    instrumentation: InstrumentationConfig = Field(default_factory=InstrumentationConfig)
