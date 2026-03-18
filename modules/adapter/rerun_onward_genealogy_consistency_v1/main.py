#!/usr/bin/env python3
"""
Selective source-aware reruns for Onward genealogy consistency targets.

This module consumes a page_html_v1 artifact plus the chapter-first consistency
report from validate_onward_genealogy_consistency_v1. It reruns only the
selected culprit pages from source images, applies conservative acceptance
checks, and preserves the original page artifact as the fallback.
"""
import argparse
import json
import os
import re
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from bs4 import BeautifulSoup

from modules.adapter.table_rescue_onward_tables_v1.main import (
    _call_ocr,
    _encode_image,
    _extract_family_labels,
    _is_generation_context_text,
    _normalize_rescue_html,
    _should_accept_rescue,
)
from modules.common.onward_genealogy_html import merge_contiguous_genealogy_tables
from modules.common.utils import ProgressLogger, ensure_dir, read_jsonl, save_json, save_jsonl
from modules.extract.ocr_ai_gpt51_v1.main import (
    _extract_code_fence,
    _extract_ocr_metadata,
    build_system_prompt,
    extract_image_metadata,
    sanitize_html,
)
from modules.validate.validate_onward_genealogy_consistency_v1.main import analyze_page_row


RERUN_HINTS = """
- This is a targeted source-aware rerun for an Onward genealogy page.
- Return HTML only for the CURRENT page image. Do not copy rows from neighbor pages.
- Use the provided schema hint and neighboring page snippets only to infer consistent structure.
- Preserve exact wording, names, punctuation, and dates from the source image.
- Use a genealogy table when the page shows genealogy rows.
- Preferred header order when visible or clearly implied: NAME, BORN, MARRIED, SPOUSE, BOY, GIRL, DIED.
- Do not merge BOY and GIRL into one column.
- Prefer subgroup labels as full-width table heading rows instead of loose paragraphs or separate mini-tables.
- Keep totals (`TOTAL DESCENDANTS`, `LIVING`, `DECEASED`) if visible on the page.
- One visual row in the source should map to one table row. Do not use <br> inside table cells for separate people.
""".strip()

SUMMARY_LABELS = ("TOTAL DESCENDANTS", "LIVING", "DECEASED")
STOP_TOKENS = {
    "THE",
    "AND",
    "NAME",
    "BORN",
    "MARRIED",
    "SPOUSE",
    "BOY",
    "GIRL",
    "DIED",
}

VALIDATOR_ISSUE_TYPE = "onward_genealogy_consistency_drift"
PLANNER_ISSUE_TYPE = "document_consistency_planning_issue"
CHAPTER_BASENAME_RE = re.compile(r"chapter-(\d+)\.html$", re.IGNORECASE)


@dataclass
class RerunTarget:
    page_number: int
    chapter_basename: str
    chapter_title: str
    schema_hint: str
    issue_reasons: List[str]
    source_pages: List[int]
    context_pages: List[int]
    target_source: str = "validator"
    issue_types: List[str] = field(default_factory=list)
    pattern_id: str = ""
    pattern_label: str = ""
    planner_status: str = ""
    planner_why: str = ""
    repair_priority: str = ""
    target_selection_notes: List[str] = field(default_factory=list)
    plan_rule_summary: List[str] = field(default_factory=list)
    plan_rule_details: Dict[str, Any] = field(default_factory=dict)
    surfaced_new_vs_current_detector: bool = False


@dataclass
class UnresolvedChapter:
    chapter_basename: str
    chapter_title: str
    source_pages: List[int]
    issue_reasons: List[str]
    issue_types: List[str] = field(default_factory=list)
    pattern_id: str = ""
    pattern_label: str = ""
    planner_status: str = ""
    planner_why: str = ""
    repair_priority: str = ""
    target_source: str = "planner_unresolved"
    target_selection_notes: List[str] = field(default_factory=list)
    plan_rule_summary: List[str] = field(default_factory=list)
    plan_rule_details: Dict[str, Any] = field(default_factory=dict)
    surfaced_new_vs_current_detector: bool = False


@dataclass
class TargetSelection:
    targets: List[RerunTarget]
    unresolved_chapters: List[UnresolvedChapter] = field(default_factory=list)
    selection_mode: str = "validator"
    artifact_paths: Dict[str, str] = field(default_factory=dict)


@dataclass
class RetentionMetrics:
    token_recall: float
    existing_text_chars: int
    candidate_text_chars: int
    text_ratio: float
    family_labels_preserved: bool
    summary_preserved: bool


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _parse_csv_ints(raw: str) -> Optional[Set[int]]:
    if not raw:
        return None
    values: Set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        values.add(int(token))
    return values


def _parse_csv_strings(raw: str) -> Optional[Set[str]]:
    if not raw:
        return None
    values = {token.strip() for token in raw.split(",") if token.strip()}
    return values or None


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_consistency_sidecar_path(report_path: str, raw_path: str) -> str:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return str(candidate)
    return str((Path(report_path).resolve().parent / candidate).resolve())


def _header_hint_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _schema_hint_from_headers(headers: Iterable[Any]) -> str:
    tokens = [_header_hint_token(value) for value in headers]
    return "|".join(token for token in tokens if token)


def _jsonl_schema_version(path: str) -> Optional[str]:
    try:
        for row in read_jsonl(path):
            schema = row.get("schema_version")
            if schema:
                return str(schema)
    except Exception:
        return None
    return None


def _coerce_page_number(row: Dict[str, Any]) -> Optional[int]:
    for key in ("page_number", "page"):
        value = row.get(key)
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _load_pages(path: str) -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]]]:
    rows = list(read_jsonl(path))
    page_map: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        page_number = _coerce_page_number(row)
        if page_number is not None:
            page_map[page_number] = row
    return rows, page_map


def _resolve_input_paths(
    *,
    pages: Optional[str],
    consistency: Optional[str],
    inputs: Optional[List[str]],
) -> Tuple[Optional[str], Optional[str]]:
    resolved_pages = pages
    resolved_consistency = consistency
    extra_inputs = list(inputs or [])
    if resolved_pages and resolved_consistency:
        return resolved_pages, resolved_consistency

    for path in extra_inputs:
        schema = _jsonl_schema_version(path)
        if schema == "page_html_v1" and not resolved_pages:
            resolved_pages = path
        elif schema == "pipeline_issues_v1" and not resolved_consistency:
            resolved_consistency = path

    if resolved_pages and resolved_consistency:
        return resolved_pages, resolved_consistency

    remaining = [path for path in extra_inputs if path not in {resolved_pages, resolved_consistency}]
    if not resolved_pages and remaining:
        resolved_pages = remaining.pop(0)
    if not resolved_consistency and remaining:
        resolved_consistency = remaining.pop(0)
    return resolved_pages, resolved_consistency


def _iter_consistency_issues(report_path: str) -> Iterable[Dict[str, Any]]:
    for row in read_jsonl(report_path):
        if row.get("schema_version") != "pipeline_issues_v1":
            continue
        for issue in row.get("issues") or []:
            yield issue


def _derive_context_pages(source_pages: List[int], page_number: int, window: int) -> List[int]:
    if window <= 0:
        return []
    return [
        candidate
        for candidate in source_pages
        if candidate != page_number and abs(candidate - page_number) <= window
    ]


def _planner_rule_summary(plan_entry: Dict[str, Any]) -> List[str]:
    rules: List[str] = []
    canonical_headers = [str(value).strip() for value in (plan_entry.get("canonical_headers") or []) if str(value).strip()]
    if canonical_headers:
        rules.append(f"Canonical headers: {' | '.join(canonical_headers)}")

    allowed_variants = [str(value).strip() for value in (plan_entry.get("allowed_variants") or []) if str(value).strip()]
    if allowed_variants:
        rules.append(f"Allowed variants: {', '.join(allowed_variants)}")

    conventions = plan_entry.get("document_local_conventions") or {}
    labels = {
        "subgroup_context_rows": "Subgroup/context rows",
        "table_fragmentation": "Table fragmentation",
        "summary_rows": "Summary rows",
        "marginal_or_handwritten_notes": "Notes policy",
    }
    for key, label in labels.items():
        value = str(conventions.get(key) or "").strip()
        if value:
            rules.append(f"{label}: {value}")
    return rules


def _cluster_consecutive_pages(page_numbers: Iterable[int]) -> List[List[int]]:
    clusters: List[List[int]] = []
    current: List[int] = []
    for page_number in sorted(set(page_numbers)):
        if not current or page_number == current[-1] + 1:
            current.append(page_number)
            continue
        clusters.append(current)
        current = [page_number]
    if current:
        clusters.append(current)
    return clusters


def _chapter_sort_key(chapter_basename: str) -> Tuple[int, str]:
    match = CHAPTER_BASENAME_RE.search(chapter_basename or "")
    if match:
        try:
            return int(match.group(1)), chapter_basename
        except ValueError:
            pass
    return 10_000, chapter_basename or ""


def _interleave_targets_by_chapter(targets: List[RerunTarget]) -> List[RerunTarget]:
    ordered: Dict[str, List[RerunTarget]] = {}
    for target in sorted(targets, key=lambda item: (_chapter_sort_key(item.chapter_basename), item.page_number)):
        ordered.setdefault(target.chapter_basename, []).append(target)

    result: List[RerunTarget] = []
    chapter_order = sorted(ordered, key=_chapter_sort_key)
    index = 0
    while True:
        added = False
        for chapter_basename in chapter_order:
            chapter_targets = ordered[chapter_basename]
            if index >= len(chapter_targets):
                continue
            result.append(chapter_targets[index])
            added = True
        if not added:
            break
        index += 1
    return result


def _planner_page_issue_score(metrics: Any, issue_types: List[str]) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []
    issues = set(issue_types or [])

    if "fragmented_multi_table_chapter" in issues:
        if metrics.table_count > 0:
            score += metrics.table_count * 20
            reasons.append(f"table_count={metrics.table_count}")
        if metrics.table_count >= 2:
            score += 40
            reasons.append("multi_table_cluster")

    if "external_family_headings" in issues and metrics.external_family_heading_count > 0:
        score += metrics.external_family_heading_count * 50
        reasons.append("external_family_headings")

    if {"residual_boygirl_headers", "fused_boygirl_headers"} & issues and metrics.residual_boygirl_header_count > 0:
        score += metrics.residual_boygirl_header_count * 60
        reasons.append("residual_boygirl_headers")

    if {"left_column_only_family_rows", "concatenated_subgroup_context_rows"} & issues and metrics.table_count > 0:
        score += 15 + (metrics.table_count * 5)
        reasons.append("table_page_for_context_fix")

    if score == 0 and issues and metrics.table_count > 0:
        score += metrics.table_count * 5
        reasons.append("fallback_table_page")

    return score, reasons


def _pick_best_planner_cluster(scored_pages: List[Dict[str, Any]], *, target_mode: str) -> List[int]:
    if not scored_pages:
        return []
    page_map = {item["page_number"]: item for item in scored_pages}
    table_pages = [item["page_number"] for item in scored_pages if item["metrics"].table_count > 0]
    if not table_pages:
        positive = [item["page_number"] for item in scored_pages if item["score"] > 0]
        if target_mode == "coarse":
            return sorted(set(positive))
        if not positive:
            return []
        best_score = max(page_map[page]["score"] for page in positive)
        return sorted(page for page in positive if page_map[page]["score"] == best_score)

    clusters = _cluster_consecutive_pages(table_pages)
    if target_mode == "coarse":
        return sorted({page for cluster in clusters for page in cluster})

    def _cluster_rank(cluster: List[int]) -> Tuple[int, int, int, int]:
        scores = [page_map[page]["score"] for page in cluster]
        return (max(scores), sum(scores), len(cluster), -cluster[0])

    best_cluster = max(clusters, key=_cluster_rank)
    return sorted(best_cluster)


def _score_planner_source_pages(
    *,
    source_pages: List[int],
    page_rows: Dict[int, Dict[str, Any]],
    issue_types: List[str],
) -> Tuple[List[Dict[str, Any]], List[int]]:
    scored_pages: List[Dict[str, Any]] = []
    missing_pages: List[int] = []
    for page_number in source_pages:
        page_row = page_rows.get(page_number)
        if page_row is None:
            missing_pages.append(page_number)
            continue
        metrics = analyze_page_row(page_row)
        score, reasons = _planner_page_issue_score(metrics, issue_types)
        if score > 0 or metrics.table_count > 0:
            scored_pages.append({
                "page_number": page_number,
                "metrics": metrics,
                "score": score,
                "reasons": reasons,
            })
    return scored_pages, missing_pages


def _describe_selected_scored_pages(
    selected_pages: List[int],
    *,
    scored_pages: List[Dict[str, Any]],
) -> List[str]:
    score_map = {item["page_number"]: item for item in scored_pages}
    return [
        f"{page}(score={score_map[page]['score']}; reasons={','.join(score_map[page]['reasons']) or 'table_page'})"
        for page in selected_pages
        if page in score_map
    ]


def _augment_explicit_planner_pages(
    explicit_pages: List[int],
    *,
    source_pages: List[int],
    page_rows: Dict[int, Dict[str, Any]],
    issue_types: List[str],
    target_mode: str,
) -> Tuple[List[int], List[str]]:
    scored_pages, missing_pages = _score_planner_source_pages(
        source_pages=source_pages,
        page_rows=page_rows,
        issue_types=issue_types,
    )
    if not scored_pages:
        notes: List[str] = []
        if missing_pages:
            notes.append(f"Source pages missing from current page_html artifact: {', '.join(str(value) for value in missing_pages)}")
        return explicit_pages, notes

    best_cluster = _pick_best_planner_cluster(scored_pages, target_mode=target_mode)
    explicit_set = set(explicit_pages)
    if explicit_set.intersection(best_cluster):
        notes = []
        if missing_pages:
            notes.append(f"Source pages missing from current page_html artifact: {', '.join(str(value) for value in missing_pages)}")
        return explicit_pages, notes

    extras = [page for page in best_cluster if page not in explicit_set]
    if not extras:
        notes = []
        if missing_pages:
            notes.append(f"Source pages missing from current page_html artifact: {', '.join(str(value) for value in missing_pages)}")
        return explicit_pages, notes

    combined = sorted(set(explicit_pages + extras))
    notes = [
        "Planner relevant_pages were augmented with source-page signals from the same chapter to catch nearby fragmentation the planner only cited indirectly.",
        f"Added pages: {', '.join(_describe_selected_scored_pages(extras, scored_pages=scored_pages))}",
    ]
    if missing_pages:
        notes.append(f"Source pages missing from current page_html artifact: {', '.join(str(value) for value in missing_pages)}")
    return combined, notes


def _build_planner_context(
    *,
    pattern_inventory: Dict[str, Any],
    consistency_plan: Dict[str, Any],
    chapter: Dict[str, Any],
    issue: Dict[str, Any],
) -> Dict[str, Any]:
    pattern_id = str(chapter.get("pattern_id") or issue.get("pattern_id") or "")
    pattern_by_id = {
        str(item.get("pattern_id") or ""): item
        for item in (pattern_inventory.get("pattern_families") or [])
        if item.get("pattern_id")
    }
    plan_by_id = {
        str(item.get("pattern_id") or ""): item
        for item in (consistency_plan.get("pattern_conventions") or [])
        if item.get("pattern_id")
    }
    pattern_entry = pattern_by_id.get(pattern_id, {})
    plan_entry = plan_by_id.get(pattern_id, {})
    label = str(plan_entry.get("label") or pattern_entry.get("label") or "")
    canonical_headers = plan_entry.get("canonical_headers") or pattern_entry.get("canonical_headers") or []
    plan_rule_details = {
        "pattern_description": str(pattern_entry.get("description") or ""),
        "baseline_chapters": list(pattern_entry.get("baseline_chapters") or []),
        "canonical_headers": list(canonical_headers),
        "canonical_signals": list(plan_entry.get("canonical_signals") or pattern_entry.get("canonical_signals") or []),
        "allowed_variants": list(plan_entry.get("allowed_variants") or pattern_entry.get("allowed_variants") or []),
        "document_local_conventions": dict(plan_entry.get("document_local_conventions") or pattern_entry.get("document_local_conventions") or {}),
    }
    return {
        "pattern_id": pattern_id,
        "pattern_label": label,
        "schema_hint": _schema_hint_from_headers(canonical_headers),
        "plan_rule_summary": _planner_rule_summary(plan_rule_details),
        "plan_rule_details": plan_rule_details,
    }


def _derive_planner_pages(
    *,
    chapter: Dict[str, Any],
    issue: Dict[str, Any],
    page_rows: Optional[Dict[int, Dict[str, Any]]],
    page_allowlist: Optional[Set[int]],
    target_mode: str,
) -> Tuple[List[int], str, List[str]]:
    explicit_pages = []
    for value in chapter.get("relevant_pages") or issue.get("relevant_pages") or []:
        try:
            explicit_pages.append(int(value))
        except (TypeError, ValueError):
            continue
    explicit_pages = sorted(set(explicit_pages))
    if explicit_pages:
        if page_allowlist is not None:
            explicit_pages = [page for page in explicit_pages if page in page_allowlist]
        notes = ["Planner relevant_pages supplied the rerun targets directly."]
        if not explicit_pages:
            return [], "planner_relevant_pages_filtered_out", notes + ["Page allowlist removed every planner-selected page."]
        issue_types = [str(value) for value in (chapter.get("issue_types") or issue.get("issue_types") or []) if value]
        source_pages = []
        for value in chapter.get("source_pages") or []:
            try:
                source_pages.append(int(value))
            except (TypeError, ValueError):
                continue
        source_pages = sorted(set(source_pages))
        if page_allowlist is not None:
            source_pages = [page for page in source_pages if page in page_allowlist]
        if page_rows and source_pages:
            explicit_pages, expansion_notes = _augment_explicit_planner_pages(
                explicit_pages,
                source_pages=source_pages,
                page_rows=page_rows,
                issue_types=issue_types,
                target_mode=target_mode,
            )
            notes.extend(expansion_notes)
            if expansion_notes:
                return explicit_pages, "planner_relevant_pages_augmented", notes
        return explicit_pages, "planner_relevant_pages", notes

    if not page_rows:
        return [], "planner_missing_page_rows_for_fallback", [
            "Planner omitted relevant_pages and no page_html rows were available for deterministic fallback.",
        ]

    issue_types = [str(value) for value in (chapter.get("issue_types") or issue.get("issue_types") or []) if value]
    source_pages = []
    for value in chapter.get("source_pages") or []:
        try:
            source_pages.append(int(value))
        except (TypeError, ValueError):
            continue
    source_pages = sorted(set(source_pages))
    if page_allowlist is not None:
        source_pages = [page for page in source_pages if page in page_allowlist]
    if not source_pages:
        return [], "planner_no_source_pages_for_fallback", [
            "Planner omitted relevant_pages and no source_pages remained after filtering.",
        ]

    scored_pages, missing_pages = _score_planner_source_pages(
        source_pages=source_pages,
        page_rows=page_rows,
        issue_types=issue_types,
    )

    if not scored_pages:
        notes = [
            "Planner omitted relevant_pages and deterministic fallback found no source page with table or issue signals.",
        ]
        if missing_pages:
            notes.append(f"Missing page rows for source pages: {', '.join(str(value) for value in missing_pages)}")
        return [], "planner_fallback_no_candidate_pages", notes

    selected_pages = _pick_best_planner_cluster(scored_pages, target_mode=target_mode)
    if not selected_pages:
        return [], "planner_fallback_no_candidate_pages", [
            "Planner omitted relevant_pages and deterministic fallback could not justify any bounded source-page target.",
        ]

    notes = [
        "Planner omitted relevant_pages; derived rerun targets from chapter source_pages plus current page_html metrics.",
        f"Selected pages: {', '.join(_describe_selected_scored_pages(selected_pages, scored_pages=scored_pages))}",
    ]
    if missing_pages:
        notes.append(f"Source pages missing from current page_html artifact: {', '.join(str(value) for value in missing_pages)}")
    return selected_pages, "planner_source_pages_fallback", notes


def _merge_target(existing: RerunTarget, candidate: RerunTarget) -> None:
    existing.issue_reasons = list(dict.fromkeys(existing.issue_reasons + candidate.issue_reasons))
    existing.issue_types = list(dict.fromkeys(existing.issue_types + candidate.issue_types))
    existing.context_pages = sorted(set(existing.context_pages + candidate.context_pages))
    existing.source_pages = sorted(set(existing.source_pages + candidate.source_pages))
    existing.target_selection_notes = list(dict.fromkeys(existing.target_selection_notes + candidate.target_selection_notes))
    existing.plan_rule_summary = list(dict.fromkeys(existing.plan_rule_summary + candidate.plan_rule_summary))
    if not existing.schema_hint and candidate.schema_hint:
        existing.schema_hint = candidate.schema_hint
    if not existing.pattern_id and candidate.pattern_id:
        existing.pattern_id = candidate.pattern_id
    if not existing.pattern_label and candidate.pattern_label:
        existing.pattern_label = candidate.pattern_label
    if not existing.planner_status and candidate.planner_status:
        existing.planner_status = candidate.planner_status
    if not existing.planner_why and candidate.planner_why:
        existing.planner_why = candidate.planner_why
    if not existing.repair_priority and candidate.repair_priority:
        existing.repair_priority = candidate.repair_priority
    if existing.target_source == "validator" and candidate.target_source != "validator":
        existing.target_source = candidate.target_source
    if not existing.plan_rule_details and candidate.plan_rule_details:
        existing.plan_rule_details = candidate.plan_rule_details
    existing.surfaced_new_vs_current_detector = (
        existing.surfaced_new_vs_current_detector or candidate.surfaced_new_vs_current_detector
    )


def _load_validator_targets(
    issues: List[Dict[str, Any]],
    *,
    target_mode: str,
    page_context_window: int,
    chapter_allowlist: Optional[Set[str]],
    page_allowlist: Optional[Set[int]],
    max_pages: int,
) -> TargetSelection:
    targets: Dict[int, RerunTarget] = {}
    for issue in issues:
        if issue.get("type") != VALIDATOR_ISSUE_TYPE:
            continue
        chapter_basename = issue.get("chapter_basename") or ""
        if chapter_allowlist and chapter_basename not in chapter_allowlist:
            continue
        source_pages = [int(page) for page in (issue.get("source_pages") or [])]
        if target_mode == "coarse":
            candidate_pages = [int(page) for page in (issue.get("coarse_suspect_pages") or [])]
        else:
            candidate_pages = [int(page) for page in (issue.get("strong_rerun_candidate_pages") or [])]
        if page_allowlist is not None:
            candidate_pages = [page for page in candidate_pages if page in page_allowlist]

        for page_number in candidate_pages:
            context_pages = _derive_context_pages(source_pages, page_number, page_context_window)
            candidate = RerunTarget(
                page_number=page_number,
                chapter_basename=chapter_basename,
                chapter_title=issue.get("chapter_title") or "",
                schema_hint=issue.get("schema_hint") or "",
                issue_reasons=list(issue.get("reasons") or []),
                source_pages=source_pages,
                context_pages=context_pages,
            )
            existing = targets.get(page_number)
            if existing is None:
                targets[page_number] = candidate
            else:
                _merge_target(existing, candidate)

    target_list = sorted(targets.values(), key=lambda item: item.page_number)
    if max_pages > 0:
        target_list = target_list[:max_pages]
    return TargetSelection(targets=target_list, selection_mode="validator")


def _load_planner_targets(
    issues: List[Dict[str, Any]],
    *,
    report_path: str,
    page_rows: Optional[Dict[int, Dict[str, Any]]],
    target_mode: str,
    page_context_window: int,
    chapter_allowlist: Optional[Set[str]],
    page_allowlist: Optional[Set[int]],
    max_pages: int,
    pattern_inventory_path: str,
    consistency_plan_path: str,
    conformance_report_path: str,
    planner_status_allowlist: Optional[Set[str]],
) -> TargetSelection:
    resolved_pattern_inventory_path = _resolve_consistency_sidecar_path(report_path, pattern_inventory_path)
    resolved_consistency_plan_path = _resolve_consistency_sidecar_path(report_path, consistency_plan_path)
    resolved_conformance_report_path = _resolve_consistency_sidecar_path(report_path, conformance_report_path)
    pattern_inventory = _load_json(resolved_pattern_inventory_path)
    consistency_plan = _load_json(resolved_consistency_plan_path)
    conformance_report = _load_json(resolved_conformance_report_path)
    chapters_by_basename = {
        str(chapter.get("chapter_basename") or ""): chapter
        for chapter in (conformance_report.get("chapters") or [])
        if chapter.get("chapter_basename")
    }

    targets: Dict[int, RerunTarget] = {}
    unresolved: List[UnresolvedChapter] = []

    for issue in issues:
        if issue.get("type") != PLANNER_ISSUE_TYPE:
            continue
        chapter_basename = issue.get("chapter_basename") or ""
        if chapter_allowlist and chapter_basename not in chapter_allowlist:
            continue
        chapter = chapters_by_basename.get(chapter_basename)
        if chapter is None:
            unresolved.append(
                UnresolvedChapter(
                    chapter_basename=chapter_basename,
                    chapter_title=issue.get("chapter_title") or "",
                    source_pages=[],
                    issue_reasons=["missing_conformance_chapter"],
                    issue_types=list(issue.get("issue_types") or []),
                    planner_status=str(issue.get("status") or ""),
                    target_selection_notes=["Primary planner report referenced a chapter absent from conformance_report.json."],
                )
            )
            continue

        planner_status = str(chapter.get("status") or issue.get("status") or "")
        if planner_status_allowlist and planner_status not in planner_status_allowlist:
            continue

        planner_context = _build_planner_context(
            pattern_inventory=pattern_inventory,
            consistency_plan=consistency_plan,
            chapter=chapter,
            issue=issue,
        )
        candidate_pages, target_source, selection_notes = _derive_planner_pages(
            chapter=chapter,
            issue=issue,
            page_rows=page_rows,
            page_allowlist=page_allowlist,
            target_mode=target_mode,
        )
        source_pages = [int(page) for page in (chapter.get("source_pages") or [])]
        issue_types = [str(value) for value in (chapter.get("issue_types") or issue.get("issue_types") or []) if value]
        issue_reasons = issue_types or [planner_status or "planner_issue"]

        if not candidate_pages:
            unresolved.append(
                UnresolvedChapter(
                    chapter_basename=chapter_basename,
                    chapter_title=chapter.get("chapter_title") or issue.get("chapter_title") or "",
                    source_pages=source_pages,
                    issue_reasons=issue_reasons,
                    issue_types=issue_types,
                    pattern_id=planner_context["pattern_id"],
                    pattern_label=planner_context["pattern_label"],
                    planner_status=planner_status,
                    planner_why=str(chapter.get("why") or ""),
                    repair_priority=str(chapter.get("repair_priority") or ""),
                    target_source=target_source,
                    target_selection_notes=selection_notes,
                    plan_rule_summary=planner_context["plan_rule_summary"],
                    plan_rule_details=planner_context["plan_rule_details"],
                    surfaced_new_vs_current_detector=bool(chapter.get("surfaced_new_vs_current_detector")),
                )
            )
            continue

        for page_number in candidate_pages:
            if page_rows is not None and page_number not in page_rows:
                unresolved.append(
                    UnresolvedChapter(
                        chapter_basename=chapter_basename,
                        chapter_title=chapter.get("chapter_title") or issue.get("chapter_title") or "",
                        source_pages=source_pages,
                        issue_reasons=issue_reasons,
                        issue_types=issue_types,
                        pattern_id=planner_context["pattern_id"],
                        pattern_label=planner_context["pattern_label"],
                        planner_status=planner_status,
                        planner_why=str(chapter.get("why") or ""),
                        repair_priority=str(chapter.get("repair_priority") or ""),
                        target_source="planner_missing_selected_page",
                        target_selection_notes=selection_notes + [f"Selected page {page_number} is absent from the current page_html artifact."],
                        plan_rule_summary=planner_context["plan_rule_summary"],
                        plan_rule_details=planner_context["plan_rule_details"],
                        surfaced_new_vs_current_detector=bool(chapter.get("surfaced_new_vs_current_detector")),
                    )
                )
                continue
            context_pages = _derive_context_pages(source_pages, page_number, page_context_window)
            candidate = RerunTarget(
                page_number=page_number,
                chapter_basename=chapter_basename,
                chapter_title=chapter.get("chapter_title") or issue.get("chapter_title") or "",
                schema_hint=planner_context["schema_hint"],
                issue_reasons=issue_reasons,
                source_pages=source_pages,
                context_pages=context_pages,
                target_source=target_source,
                issue_types=issue_types,
                pattern_id=planner_context["pattern_id"],
                pattern_label=planner_context["pattern_label"],
                planner_status=planner_status,
                planner_why=str(chapter.get("why") or ""),
                repair_priority=str(chapter.get("repair_priority") or ""),
                target_selection_notes=selection_notes,
                plan_rule_summary=planner_context["plan_rule_summary"],
                plan_rule_details=planner_context["plan_rule_details"],
                surfaced_new_vs_current_detector=bool(chapter.get("surfaced_new_vs_current_detector")),
            )
            existing = targets.get(page_number)
            if existing is None:
                targets[page_number] = candidate
            else:
                _merge_target(existing, candidate)

    target_list = _interleave_targets_by_chapter(list(targets.values()))
    if max_pages > 0:
        target_list = target_list[:max_pages]
    return TargetSelection(
        targets=target_list,
        unresolved_chapters=unresolved,
        selection_mode="planner",
        artifact_paths={
            "consistency_report": report_path,
            "pattern_inventory": resolved_pattern_inventory_path,
            "consistency_plan": resolved_consistency_plan_path,
            "conformance_report": resolved_conformance_report_path,
        },
    )


def load_targets(
    report_path: str,
    *,
    page_rows: Optional[Dict[int, Dict[str, Any]]] = None,
    target_mode: str,
    page_context_window: int,
    chapter_allowlist: Optional[Set[str]],
    page_allowlist: Optional[Set[int]],
    max_pages: int,
    pattern_inventory_path: str = "pattern_inventory.json",
    consistency_plan_path: str = "consistency_plan.json",
    conformance_report_path: str = "conformance_report.json",
    planner_status_allowlist: Optional[Set[str]] = None,
    return_selection: bool = False,
) -> Any:
    issues = list(_iter_consistency_issues(report_path))
    issue_types = {str(issue.get("type") or "") for issue in issues}
    if PLANNER_ISSUE_TYPE in issue_types:
        selection = _load_planner_targets(
            issues,
            report_path=report_path,
            page_rows=page_rows,
            target_mode=target_mode,
            page_context_window=page_context_window,
            chapter_allowlist=chapter_allowlist,
            page_allowlist=page_allowlist,
            max_pages=max_pages,
            pattern_inventory_path=pattern_inventory_path,
            consistency_plan_path=consistency_plan_path,
            conformance_report_path=conformance_report_path,
            planner_status_allowlist=planner_status_allowlist or {"format_drift"},
        )
    else:
        selection = _load_validator_targets(
            issues,
            target_mode=target_mode,
            page_context_window=page_context_window,
            chapter_allowlist=chapter_allowlist,
            page_allowlist=page_allowlist,
            max_pages=max_pages,
        )
    return selection if return_selection else selection.targets


def _best_effort_normalize_html(html: str) -> str:
    cleaned = sanitize_html(html or "")
    cleaned = merge_contiguous_genealogy_tables(
        cleaned,
        rescue_normalizer=_normalize_rescue_html,
    )
    return _restore_subgroup_row_markers(cleaned)


def _html_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def _family_labels_from_html(html: str) -> Set[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    labels: Set[str] = set()
    for tag in soup.find_all(["h1", "h2", "h3", "p", "th", "td", "li"]):
        for fragment in tag.stripped_strings:
            text = re.sub(r"\s+", " ", fragment).strip()
            if not text:
                continue
            labels.update(_extract_family_labels(text.upper()))
    return labels


def _table_column_count(table: Any) -> int:
    max_cols = 0
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        max_cols = max(max_cols, len(cells))
    return max_cols or 1


def _restore_subgroup_row_markers(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for table in soup.find_all("table"):
        colspan = _table_column_count(table)
        tbody = table.find("tbody", recursive=False)
        if tbody is not None:
            rows = tbody.find_all("tr", recursive=False)
        else:
            rows = table.find_all("tr", recursive=False)[1:]

        for row in rows:
            if "genealogy-subgroup-heading" in (row.get("class") or []):
                continue
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) != 1:
                continue
            text = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True)).strip()
            if not text:
                continue
            if not (_extract_family_labels(text.upper()) or _is_generation_context_text(text)):
                continue
            row["class"] = "genealogy-subgroup-heading"
            cells[0].name = "th"
            cells[0]["colspan"] = str(colspan)
    return str(soup)


def _text_tokens(text: str) -> List[str]:
    tokens = [
        token.upper()
        for token in re.findall(r"[A-Za-z0-9']+", text or "")
        if len(token) > 1
    ]
    return [token for token in tokens if token not in STOP_TOKENS]


def _content_retention_metrics(existing_html: str, candidate_html: str) -> RetentionMetrics:
    existing_text = _html_text(existing_html)
    candidate_text = _html_text(candidate_html)
    existing_tokens = _text_tokens(existing_text)
    candidate_token_set = set(_text_tokens(candidate_text))
    if existing_tokens:
        matched = sum(1 for token in existing_tokens if token in candidate_token_set)
        token_recall = round(matched / len(existing_tokens), 4)
    else:
        token_recall = 1.0

    existing_upper = existing_text.upper()
    candidate_upper = candidate_text.upper()
    existing_family_labels = _family_labels_from_html(existing_html)
    candidate_family_labels = _family_labels_from_html(candidate_html)
    existing_summary = {label for label in SUMMARY_LABELS if label in existing_upper}
    candidate_summary = {label for label in SUMMARY_LABELS if label in candidate_upper}

    existing_chars = len(existing_text)
    candidate_chars = len(candidate_text)
    text_ratio = round(candidate_chars / existing_chars, 4) if existing_chars else 1.0

    return RetentionMetrics(
        token_recall=token_recall,
        existing_text_chars=existing_chars,
        candidate_text_chars=candidate_chars,
        text_ratio=text_ratio,
        family_labels_preserved=existing_family_labels.issubset(candidate_family_labels),
        summary_preserved=existing_summary.issubset(candidate_summary),
    )


def _retention_gate(
    existing_html: str,
    candidate_html: str,
    *,
    min_token_recall: float,
    min_text_ratio: float,
) -> Tuple[bool, str, RetentionMetrics]:
    metrics = _content_retention_metrics(existing_html, candidate_html)
    if not metrics.summary_preserved:
        return False, "candidate_lost_summary_labels", metrics
    if not metrics.family_labels_preserved:
        return False, "candidate_lost_family_labels", metrics
    if metrics.token_recall < min_token_recall:
        return False, "candidate_token_recall_too_low", metrics
    if metrics.existing_text_chars >= 120 and metrics.text_ratio < min_text_ratio:
        return False, "candidate_text_ratio_too_low", metrics
    return True, "candidate_content_retained", metrics


def _page_drift_penalty(metrics: Any) -> int:
    penalty = 0
    penalty += metrics.residual_boygirl_header_count * 40
    penalty += metrics.external_family_heading_count * 25
    if metrics.table_count >= 2:
        penalty += max(metrics.table_count - 1, 0) * 5
        if metrics.subgroup_row_count == 0:
            penalty += 15
    return penalty


def _page_drift_gate(existing_html: str, candidate_html: str) -> Tuple[bool, str, Dict[str, Any], Dict[str, Any]]:
    existing_metrics = analyze_page_row({"html": existing_html})
    candidate_metrics = analyze_page_row({"html": candidate_html})
    existing_dict = asdict(existing_metrics)
    candidate_dict = asdict(candidate_metrics)

    if candidate_metrics.residual_boygirl_header_count > existing_metrics.residual_boygirl_header_count:
        return False, "candidate_worsened_boygirl_headers", existing_dict, candidate_dict
    if candidate_metrics.external_family_heading_count > existing_metrics.external_family_heading_count:
        return False, "candidate_worsened_external_family_headings", existing_dict, candidate_dict

    existing_penalty = _page_drift_penalty(existing_metrics)
    candidate_penalty = _page_drift_penalty(candidate_metrics)
    if candidate_penalty < existing_penalty:
        return True, "candidate_drift_reduced", existing_dict, candidate_dict
    if candidate_penalty > existing_penalty:
        return False, "candidate_drift_worsened", existing_dict, candidate_dict
    return True, "candidate_drift_not_worsened", existing_dict, candidate_dict


def _evaluate_candidate(
    existing_html: str,
    candidate_html: str,
    *,
    min_score_gain: int,
    min_token_recall: float,
    min_text_ratio: float,
) -> Dict[str, Any]:
    accepted_page, page_reason, existing_quality, candidate_quality = _should_accept_rescue(
        existing_html,
        candidate_html,
        0.8,
        min_score_gain,
    )
    retention_ok, retention_reason, retention_metrics = _retention_gate(
        existing_html,
        candidate_html,
        min_token_recall=min_token_recall,
        min_text_ratio=min_text_ratio,
    )
    drift_ok, drift_reason, existing_page_metrics, candidate_page_metrics = _page_drift_gate(
        existing_html,
        candidate_html,
    )
    accepted = retention_ok and drift_ok and (accepted_page or drift_reason == "candidate_drift_reduced")
    if accepted:
        decision_reason = "candidate_accepted" if accepted_page else "candidate_drift_reduced"
    else:
        if not retention_ok:
            decision_reason = retention_reason
        elif not drift_ok:
            decision_reason = drift_reason
        else:
            decision_reason = page_reason
    return {
        "accepted": accepted,
        "decision_reason": decision_reason,
        "existing_quality": asdict(existing_quality),
        "candidate_quality": asdict(candidate_quality),
        "retention_metrics": asdict(retention_metrics),
        "existing_page_metrics": existing_page_metrics,
        "candidate_page_metrics": candidate_page_metrics,
        "page_drift_reason": drift_reason,
    }


def _context_snippet(page_row: Dict[str, Any]) -> str:
    page_number = _coerce_page_number(page_row)
    printed = page_row.get("printed_page_number")
    html = page_row.get("html") or page_row.get("raw_html") or ""
    snippet = html.strip()
    if len(snippet) > 1400:
        snippet = snippet[:1400].rstrip() + "\n..."
    return (
        f"Page {page_number}"
        f"{f' (printed {printed})' if printed is not None else ''}:\n"
        f"{snippet}"
    )


def build_user_text(
    target: RerunTarget,
    page_rows: Dict[int, Dict[str, Any]],
    *,
    max_context_chars: int,
) -> str:
    current_row = page_rows[target.page_number]
    current_html = (current_row.get("html") or current_row.get("raw_html") or "").strip()
    parts = [
        "Return HTML for the CURRENT target page image only.",
        "Use neighboring snippets only as a consistency hint. Do not copy rows that are not visible on the target page image.",
        f"Target page: {target.page_number}",
    ]
    if current_row.get("printed_page_number") is not None:
        parts.append(f"Printed page number: {current_row['printed_page_number']}")
    if target.chapter_basename:
        parts.append(f"Chapter artifact: {target.chapter_basename}")
    if target.chapter_title:
        parts.append(f"Chapter title: {target.chapter_title}")
    if target.schema_hint:
        parts.append(f"Frozen schema hint: {target.schema_hint}")
    if target.issue_reasons:
        parts.append(f"Consistency reasons: {', '.join(target.issue_reasons)}")
    if target.pattern_label:
        pattern_text = target.pattern_label
        if target.pattern_id:
            pattern_text += f" ({target.pattern_id})"
        parts.append(f"Pattern family: {pattern_text}")
    if target.planner_status:
        parts.append(f"Planner status: {target.planner_status}")
    if target.issue_types:
        parts.append(f"Planner issue types: {', '.join(target.issue_types)}")
    if target.planner_why:
        parts.append(f"Planner conformance reason: {target.planner_why}")
    if target.plan_rule_summary:
        parts.append("Consistency plan guidance:")
        parts.extend(f"- {rule}" for rule in target.plan_rule_summary[:5])
    if target.target_selection_notes:
        parts.append(f"Target selection notes: {' | '.join(target.target_selection_notes[:3])}")

    parts.append("\nCurrent extracted HTML for the target page (may be structurally wrong):\n")
    parts.append(current_html[:max_context_chars])

    remaining = max(0, max_context_chars - len(current_html))
    if target.context_pages and remaining > 200:
        parts.append("\nNeighbor page context:\n")
        for page_number in target.context_pages:
            page_row = page_rows.get(page_number)
            if not page_row:
                continue
            snippet = _context_snippet(page_row)
            if len(snippet) > remaining:
                snippet = snippet[:remaining].rstrip() + "\n..."
            parts.append(snippet)
            remaining -= len(snippet)
            if remaining <= 0:
                break

    return "\n".join(parts)


def _build_prompt(extra_hints: Optional[str]) -> str:
    hints = RERUN_HINTS
    if extra_hints:
        hints += "\n" + extra_hints.strip()
    return build_system_prompt(hints)


def _report_path(base_out: str, raw_path: str) -> str:
    if os.path.isabs(raw_path) or os.path.sep in raw_path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (Path.cwd() / raw_path).resolve()
        return str(candidate)
    return str(Path(base_out).resolve().parent / raw_path)


def _apply_candidate(
    row: Dict[str, Any],
    raw_response: str,
    normalized_html: str,
    meta: Optional[Dict[str, Any]],
    meta_tag: Optional[str],
    meta_warning: Optional[str],
) -> None:
    meta = meta or {}
    if meta:
        row.update({key: value for key, value in meta.items() if value is not None})
    if meta_warning:
        row["ocr_metadata_warning"] = meta_warning
    if meta_tag and not all(value is not None for value in meta.values()):
        row["ocr_metadata_tag"] = meta_tag
    if not meta_tag:
        row["ocr_metadata_missing"] = True
    row["raw_html"] = raw_response
    row["html"] = normalized_html
    images = extract_image_metadata(normalized_html)
    if images:
        row["images"] = images


def _usage_to_dict(usage: Any) -> Any:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if hasattr(usage, "dict"):
        return usage.dict()
    if hasattr(usage, "__dict__"):
        return usage.__dict__
    return usage


def run_reruns(
    rows: List[Dict[str, Any]],
    page_rows: Dict[int, Dict[str, Any]],
    targets: List[RerunTarget],
    *,
    unresolved_chapters: Optional[List[UnresolvedChapter]] = None,
    selection_mode: str = "validator",
    planner_artifact_paths: Optional[Dict[str, str]] = None,
    report_path: str,
    summary_path: str,
    pages_artifact_path: str,
    consistency_report_path: str,
    out_path: str,
    model: str,
    temperature: float,
    max_output_tokens: int,
    timeout_seconds: Optional[float],
    max_context_chars: int,
    min_score_gain: int,
    min_token_recall: float,
    min_text_ratio: float,
    prompt: str,
    run_id: Optional[str],
    progress_file: Optional[str],
    state_file: Optional[str],
) -> None:
    target_map = {target.page_number: target for target in targets}
    report_rows: List[Dict[str, Any]] = []
    out_rows: List[Dict[str, Any]] = []
    unresolved_chapters = list(unresolved_chapters or [])
    planner_artifact_paths = dict(planner_artifact_paths or {})

    logger = ProgressLogger(state_path=state_file, progress_path=progress_file, run_id=run_id)
    logger.log(
        "adapter",
        "running",
        current=0,
        total=max(1, len(target_map)),
        message="Running Onward genealogy source-aware reruns",
        artifact=out_path,
        module_id="rerun_onward_genealogy_consistency_v1",
        schema_version="page_html_v1",
        extra={
            "consistency_report": consistency_report_path,
            "selection_mode": selection_mode,
            **planner_artifact_paths,
        },
    )

    processed_targets = 0
    accepted_count = 0
    deterministic_normalized_count = 0
    deterministic_normalized_pages: List[int] = []
    rejection_reasons: Dict[str, int] = {}
    target_sources: Dict[str, int] = {}

    for unresolved in unresolved_chapters:
        report_rows.append({
            "page_number": None,
            "chapter_basename": unresolved.chapter_basename,
            "chapter_title": unresolved.chapter_title,
            "schema_hint": "",
            "issue_reasons": unresolved.issue_reasons,
            "issue_types": unresolved.issue_types,
            "pattern_id": unresolved.pattern_id or None,
            "pattern_label": unresolved.pattern_label or None,
            "planner_status": unresolved.planner_status or None,
            "planner_why": unresolved.planner_why or None,
            "repair_priority": unresolved.repair_priority or None,
            "plan_rule_summary": unresolved.plan_rule_summary,
            "plan_rule_details": unresolved.plan_rule_details,
            "source_pages": unresolved.source_pages,
            "context_pages": [],
            "target_source": unresolved.target_source,
            "target_selection_notes": unresolved.target_selection_notes,
            "surfaced_new_vs_current_detector": unresolved.surfaced_new_vs_current_detector,
            "targeted": False,
            "accepted": False,
            "decision_reason": unresolved.target_source,
            "unresolved": True,
            "input_pages_artifact_path": pages_artifact_path,
            "output_pages_artifact_path": out_path,
            "consistency_report_artifact_path": consistency_report_path,
            "selection_mode": selection_mode,
            **planner_artifact_paths,
        })

    for row in rows:
        page_number = _coerce_page_number(row)
        new_row = deepcopy(row)
        new_row["module_id"] = "rerun_onward_genealogy_consistency_v1"
        if run_id:
            new_row["run_id"] = run_id
        new_row["created_at"] = _utc()
        existing_html = row.get("html") or row.get("raw_html") or ""
        normalized_existing = _best_effort_normalize_html(existing_html)
        normalized_eval = None
        if normalized_existing != existing_html:
            normalized_eval = _evaluate_candidate(
                existing_html,
                normalized_existing,
                min_score_gain=min_score_gain,
                min_token_recall=min_token_recall,
                min_text_ratio=min_text_ratio,
            )

        target = target_map.get(page_number or -1)
        if target is None:
            if normalized_eval and normalized_eval["accepted"]:
                deterministic_normalized_count += 1
                deterministic_normalized_pages.append(page_number)
                new_row["html"] = normalized_existing
                report_rows.append({
                    "page_number": page_number,
                    "chapter_basename": None,
                    "chapter_title": None,
                    "schema_hint": "",
                    "issue_reasons": [],
                    "issue_types": [],
                    "pattern_id": None,
                    "pattern_label": None,
                    "planner_status": None,
                    "planner_why": None,
                    "repair_priority": None,
                    "plan_rule_summary": [],
                    "plan_rule_details": {},
                    "source_pages": [],
                    "context_pages": [],
                    "target_source": "deterministic_normalization",
                    "target_selection_notes": [
                        "Applied deterministic genealogy normalization because the existing page HTML improved without requiring OCR.",
                    ],
                    "surfaced_new_vs_current_detector": False,
                    "targeted": False,
                    "accepted": True,
                    "decision_reason": "deterministic_normalization_accepted",
                    "request_id": None,
                    "usage": None,
                    "existing_html": existing_html,
                    "normalized_existing_html": normalized_existing,
                    "normalized_existing_changed": True,
                    "normalized_existing_accepted": True,
                    "normalized_existing_decision_reason": normalized_eval["decision_reason"],
                    "normalized_existing_quality": normalized_eval["candidate_quality"],
                    "normalized_existing_retention_metrics": normalized_eval["retention_metrics"],
                    "normalized_existing_page_metrics": normalized_eval["candidate_page_metrics"],
                    "existing_quality": normalized_eval["existing_quality"],
                    "candidate_quality": normalized_eval["candidate_quality"],
                    "retention_metrics": normalized_eval["retention_metrics"],
                    "existing_page_metrics": normalized_eval["existing_page_metrics"],
                    "candidate_page_metrics": normalized_eval["candidate_page_metrics"],
                    "page_drift_reason": normalized_eval["page_drift_reason"],
                    "candidate_html": normalized_existing,
                    "final_html": normalized_existing,
                    "input_pages_artifact_path": pages_artifact_path,
                    "output_pages_artifact_path": out_path,
                    "consistency_report_artifact_path": consistency_report_path,
                    "selection_mode": selection_mode,
                    **planner_artifact_paths,
                })
            out_rows.append(new_row)
            continue

        processed_targets += 1
        image_path = row.get("image")
        report_record: Dict[str, Any] = {
            "page_number": page_number,
            "chapter_basename": target.chapter_basename,
            "chapter_title": target.chapter_title,
            "schema_hint": target.schema_hint,
            "issue_reasons": target.issue_reasons,
            "issue_types": target.issue_types,
            "pattern_id": target.pattern_id or None,
            "pattern_label": target.pattern_label or None,
            "planner_status": target.planner_status or None,
            "planner_why": target.planner_why or None,
            "repair_priority": target.repair_priority or None,
            "plan_rule_summary": target.plan_rule_summary,
            "plan_rule_details": target.plan_rule_details,
            "source_pages": target.source_pages,
            "context_pages": target.context_pages,
            "target_source": target.target_source,
            "target_selection_notes": target.target_selection_notes,
            "surfaced_new_vs_current_detector": target.surfaced_new_vs_current_detector,
            "source_image": image_path,
            "input_pages_artifact_path": pages_artifact_path,
            "output_pages_artifact_path": out_path,
            "consistency_report_artifact_path": consistency_report_path,
            "model": model,
            "existing_html": row.get("html") or row.get("raw_html") or "",
            "selection_mode": selection_mode,
            **planner_artifact_paths,
        }
        target_sources[target.target_source] = target_sources.get(target.target_source, 0) + 1

        logger.log(
            "adapter",
            "running",
            current=processed_targets,
            total=max(1, len(target_map)),
            message=f"Rerunning genealogy page {page_number}",
            artifact=out_path,
            module_id="rerun_onward_genealogy_consistency_v1",
            schema_version="page_html_v1",
        )

        if not image_path or not os.path.exists(image_path):
            report_record.update({
                "targeted": True,
                "accepted": False,
                "decision_reason": "missing_image",
            })
            rejection_reasons["missing_image"] = rejection_reasons.get("missing_image", 0) + 1
            report_rows.append(report_record)
            out_rows.append(new_row)
            continue

        report_record["normalized_existing_html"] = normalized_existing
        report_record["normalized_existing_changed"] = normalized_existing != existing_html
        if normalized_eval is not None:
            report_record.update({
                "normalized_existing_accepted": normalized_eval["accepted"],
                "normalized_existing_decision_reason": normalized_eval["decision_reason"],
                "normalized_existing_quality": normalized_eval["candidate_quality"],
                "normalized_existing_retention_metrics": normalized_eval["retention_metrics"],
                "normalized_existing_page_metrics": normalized_eval["candidate_page_metrics"],
            })
            if normalized_eval["accepted"]:
                accepted_count += 1
                new_row["html"] = normalized_existing
                report_record.update({
                    "targeted": True,
                    "accepted": True,
                    "decision_reason": "normalized_existing_accepted",
                    "request_id": None,
                    "usage": None,
                    "existing_quality": normalized_eval["existing_quality"],
                    "candidate_quality": normalized_eval["candidate_quality"],
                    "retention_metrics": normalized_eval["retention_metrics"],
                    "existing_page_metrics": normalized_eval["existing_page_metrics"],
                    "candidate_page_metrics": normalized_eval["candidate_page_metrics"],
                    "page_drift_reason": normalized_eval["page_drift_reason"],
                    "candidate_html": normalized_existing,
                    "final_html": new_row.get("html") or new_row.get("raw_html") or "",
                })
                report_rows.append(report_record)
                out_rows.append(new_row)
                continue

        image_data = _encode_image(image_path)
        user_text = build_user_text(target, page_rows, max_context_chars=max_context_chars)

        try:
            raw_response, usage, request_id = _call_ocr(
                model,
                prompt,
                image_data,
                temperature,
                max_output_tokens,
                timeout_seconds,
                user_text=user_text,
            )
        except Exception as exc:  # pragma: no cover - network/environment dependent
            report_record.update({
                "targeted": True,
                "accepted": False,
                "decision_reason": "ocr_error",
                "error": str(exc),
            })
            rejection_reasons["ocr_error"] = rejection_reasons.get("ocr_error", 0) + 1
            report_rows.append(report_record)
            out_rows.append(new_row)
            continue

        raw_response = _extract_code_fence(raw_response)
        cleaned_raw, meta, meta_tag, meta_warning = _extract_ocr_metadata(raw_response)
        normalized_candidate = _best_effort_normalize_html(cleaned_raw)
        candidate_eval = _evaluate_candidate(
            existing_html,
            normalized_candidate,
            min_score_gain=min_score_gain,
            min_token_recall=min_token_recall,
            min_text_ratio=min_text_ratio,
        )
        accepted = candidate_eval["accepted"]
        if accepted:
            accepted_count += 1
            _apply_candidate(new_row, raw_response, normalized_candidate, meta, meta_tag, meta_warning)
            decision_reason = candidate_eval["decision_reason"]
        else:
            decision_reason = candidate_eval["decision_reason"]
            rejection_reasons[decision_reason] = rejection_reasons.get(decision_reason, 0) + 1

        report_record.update({
            "targeted": True,
            "accepted": accepted,
            "decision_reason": decision_reason,
            "request_id": request_id,
            "usage": _usage_to_dict(usage),
            "existing_quality": candidate_eval["existing_quality"],
            "candidate_quality": candidate_eval["candidate_quality"],
            "retention_metrics": candidate_eval["retention_metrics"],
            "existing_page_metrics": candidate_eval["existing_page_metrics"],
            "candidate_page_metrics": candidate_eval["candidate_page_metrics"],
            "page_drift_reason": candidate_eval["page_drift_reason"],
            "candidate_html": normalized_candidate,
            "final_html": new_row.get("html") or new_row.get("raw_html") or "",
        })
        report_rows.append(report_record)
        out_rows.append(new_row)

    summary = {
        "schema_version": "onward_genealogy_rerun_summary_v1",
        "module_id": "rerun_onward_genealogy_consistency_v1",
        "created_at": _utc(),
        "run_id": run_id,
        "input_pages_artifact_path": pages_artifact_path,
        "consistency_report_artifact_path": consistency_report_path,
        "output_pages_artifact_path": out_path,
        "targeted_page_count": len(target_map),
        "targeted_pages": sorted(target_map),
        "selection_mode": selection_mode,
        "target_sources": target_sources,
        "accepted_page_count": accepted_count,
        "rejected_page_count": len(target_map) - accepted_count,
        "deterministic_normalized_page_count": deterministic_normalized_count,
        "deterministic_normalized_pages": sorted(page for page in deterministic_normalized_pages if page is not None),
        "rejection_reasons": rejection_reasons,
        "chapters": sorted({target.chapter_basename for target in targets}),
        "unresolved_chapter_count": len(unresolved_chapters),
        "unresolved_chapters": [chapter.chapter_basename for chapter in unresolved_chapters],
        **planner_artifact_paths,
    }

    save_jsonl(out_path, out_rows)
    save_jsonl(report_path, report_rows)
    save_json(summary_path, summary)

    logger.log(
        "adapter",
        "done",
        current=len(target_map),
        total=max(1, len(target_map)),
        message=f"Onward genealogy reruns complete: accepted={accepted_count}/{len(target_map)}",
        artifact=out_path,
        module_id="rerun_onward_genealogy_consistency_v1",
        schema_version="page_html_v1",
        extra={"report": report_path, "summary_report": summary_path},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Selective source-aware reruns for Onward genealogy consistency targets.")
    parser.add_argument("--pages", help="Input page_html_v1 JSONL")
    parser.add_argument("--consistency", help="pipeline_issues_v1 JSONL from validate_onward_genealogy_consistency_v1")
    parser.add_argument("--inputs", nargs="*", help="Driver compatibility: pages JSONL plus consistency JSONL")
    parser.add_argument("--out", required=True, help="Output page_html_v1 JSONL path")
    parser.add_argument("--report", default="rerun_onward_genealogy_report.jsonl")
    parser.add_argument("--summary-report", dest="summary_report", default="rerun_onward_genealogy_summary.json")
    parser.add_argument("--summary_report", dest="summary_report", default="rerun_onward_genealogy_summary.json")
    parser.add_argument("--pattern-inventory", dest="pattern_inventory", default="pattern_inventory.json")
    parser.add_argument("--pattern_inventory", dest="pattern_inventory", default="pattern_inventory.json")
    parser.add_argument("--consistency-plan", dest="consistency_plan", default="consistency_plan.json")
    parser.add_argument("--consistency_plan", dest="consistency_plan", default="consistency_plan.json")
    parser.add_argument("--conformance-report", dest="conformance_report", default="conformance_report.json")
    parser.add_argument("--conformance_report", dest="conformance_report", default="conformance_report.json")
    parser.add_argument("--planner-status-allowlist", dest="planner_status_allowlist", default="format_drift")
    parser.add_argument("--planner_status_allowlist", dest="planner_status_allowlist", default="format_drift")
    parser.add_argument("--model", default="gpt-5")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-output-tokens", dest="max_output_tokens", type=int, default=32768)
    parser.add_argument("--max_output_tokens", dest="max_output_tokens", type=int, default=32768)
    parser.add_argument("--timeout-seconds", dest="timeout_seconds", type=float, default=120.0)
    parser.add_argument("--timeout_seconds", dest="timeout_seconds", type=float, default=120.0)
    parser.add_argument("--max-context-chars", dest="max_context_chars", type=int, default=6000)
    parser.add_argument("--max_context_chars", dest="max_context_chars", type=int, default=6000)
    parser.add_argument("--page-context-window", dest="page_context_window", type=int, default=1)
    parser.add_argument("--page_context_window", dest="page_context_window", type=int, default=1)
    parser.add_argument("--min-score-gain", dest="min_score_gain", type=int, default=15)
    parser.add_argument("--min_score_gain", dest="min_score_gain", type=int, default=15)
    parser.add_argument("--min-token-recall", dest="min_token_recall", type=float, default=0.75)
    parser.add_argument("--min_token_recall", dest="min_token_recall", type=float, default=0.75)
    parser.add_argument("--min-text-ratio", dest="min_text_ratio", type=float, default=0.65)
    parser.add_argument("--min_text_ratio", dest="min_text_ratio", type=float, default=0.65)
    parser.add_argument("--target-mode", dest="target_mode", choices=("strong", "coarse"), default="strong")
    parser.add_argument("--target_mode", dest="target_mode", choices=("strong", "coarse"), default="strong")
    parser.add_argument("--chapter-allowlist", dest="chapter_allowlist", default="")
    parser.add_argument("--chapter_allowlist", dest="chapter_allowlist", default="")
    parser.add_argument("--page-allowlist", dest="page_allowlist", default="")
    parser.add_argument("--page_allowlist", dest="page_allowlist", default="")
    parser.add_argument("--max-pages", dest="max_pages", type=int, default=10)
    parser.add_argument("--max_pages", dest="max_pages", type=int, default=10)
    parser.add_argument("--rescue-hints", dest="rescue_hints", default=None)
    parser.add_argument("--rescue_hints", dest="rescue_hints", default=None)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    pages_path, consistency_path = _resolve_input_paths(
        pages=args.pages,
        consistency=args.consistency,
        inputs=args.inputs,
    )
    if not pages_path:
        raise SystemExit("Missing --pages/--inputs page_html_v1 artifact")
    if not consistency_path:
        raise SystemExit("Missing --consistency/--inputs pipeline_issues_v1 artifact")
    if not os.path.exists(pages_path):
        raise SystemExit(f"Missing pages artifact: {pages_path}")
    if not os.path.exists(consistency_path):
        raise SystemExit(f"Missing consistency report: {consistency_path}")

    out_path = os.path.abspath(args.out)
    ensure_dir(os.path.dirname(out_path) or ".")
    report_path = _report_path(out_path, args.report)
    summary_path = _report_path(out_path, args.summary_report)

    rows, page_rows = _load_pages(pages_path)
    selection = load_targets(
        consistency_path,
        page_rows=page_rows,
        target_mode=args.target_mode,
        page_context_window=args.page_context_window,
        chapter_allowlist=_parse_csv_strings(args.chapter_allowlist),
        page_allowlist=_parse_csv_ints(args.page_allowlist),
        max_pages=args.max_pages,
        pattern_inventory_path=args.pattern_inventory,
        consistency_plan_path=args.consistency_plan,
        conformance_report_path=args.conformance_report,
        planner_status_allowlist=_parse_csv_strings(args.planner_status_allowlist),
        return_selection=True,
    )
    prompt = _build_prompt(args.rescue_hints)

    run_reruns(
        rows,
        page_rows,
        selection.targets,
        unresolved_chapters=selection.unresolved_chapters,
        selection_mode=selection.selection_mode,
        planner_artifact_paths=selection.artifact_paths,
        report_path=report_path,
        summary_path=summary_path,
        pages_artifact_path=pages_path,
        consistency_report_path=consistency_path,
        out_path=out_path,
        model=args.model,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        timeout_seconds=args.timeout_seconds,
        max_context_chars=args.max_context_chars,
        min_score_gain=args.min_score_gain,
        min_token_recall=args.min_token_recall,
        min_text_ratio=args.min_text_ratio,
        prompt=prompt,
        run_id=args.run_id,
        progress_file=args.progress_file,
        state_file=args.state_file,
    )


if __name__ == "__main__":
    main()
