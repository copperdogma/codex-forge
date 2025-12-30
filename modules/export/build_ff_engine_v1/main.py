import argparse
import json
import os
from typing import Any, Dict, List, Optional

from modules.common.utils import read_jsonl, save_json, ProgressLogger
from modules.common.html_utils import html_to_text


def _append_nav(
    nav: List[Dict[str, Any]],
    seen: set,
    *,
    target: Optional[Any],
    kind: str,
    outcome: Optional[str] = None,
    choice_text: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> None:
    if target is None:
        return
    entry: Dict[str, Any] = {"targetSection": str(target), "kind": kind}
    if outcome:
        entry["outcome"] = outcome
    if choice_text:
        entry["choiceText"] = choice_text
    if params:
        entry["params"] = params
    key = (
        entry["targetSection"],
        entry.get("kind"),
        entry.get("outcome"),
        entry.get("choiceText"),
        json.dumps(entry.get("params"), sort_keys=True) if entry.get("params") is not None else None,
    )
    if key in seen:
        return
    seen.add(key)
    nav.append(entry)


def make_navigation(portion: Dict[str, Any]) -> List[Dict[str, Any]]:
    choice_nav: List[Dict[str, Any]] = []
    mech_nav: List[Dict[str, Any]] = []
    choice_seen: set = set()
    mech_seen: set = set()
    for choice in portion.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        _append_nav(
            choice_nav,
            choice_seen,
            target=choice.get("target"),
            kind="choice",
            choice_text=choice.get("text"),
        )
    if not choice_nav:
        # Fall back to targets list if present
        for tgt in portion.get("targets") or []:
            _append_nav(choice_nav, choice_seen, target=tgt, kind="choice")

    # Test Your Luck
    for ty in portion.get("testYourLuck") or []:
        if not isinstance(ty, dict):
            continue
        _append_nav(mech_nav, mech_seen, target=ty.get("luckySection"), kind="test_luck", outcome="lucky")
        _append_nav(mech_nav, mech_seen, target=ty.get("unluckySection"), kind="test_luck", outcome="unlucky")

    # Item checks
    for item in portion.get("items") or []:
        if not isinstance(item, dict):
            continue
        if item.get("action") != "check":
            continue
        params = {"itemName": item.get("name")} if item.get("name") else None
        _append_nav(mech_nav, mech_seen, target=item.get("checkSuccessSection"), kind="item_check", outcome="has_item", params=params)
        _append_nav(mech_nav, mech_seen, target=item.get("checkFailureSection"), kind="item_check", outcome="no_item", params=params)

    # Combat outcomes
    combat = portion.get("combat")
    combat_list = [combat] if isinstance(combat, dict) else (combat or [])
    for c in combat_list:
        if not isinstance(c, dict):
            continue
        params = {"enemy": c.get("name") or c.get("enemy")} if (c.get("name") or c.get("enemy")) else None
        _append_nav(mech_nav, mech_seen, target=c.get("winSection"), kind="combat", outcome="win", params=params)
        _append_nav(mech_nav, mech_seen, target=c.get("loseSection"), kind="combat", outcome="lose", params=params)
        _append_nav(mech_nav, mech_seen, target=c.get("escapeSection"), kind="combat", outcome="escape", params=params)

    # Death conditions
    for death in portion.get("deathConditions") or []:
        if not isinstance(death, dict):
            continue
        params = None
        if death.get("description"):
            params = {"description": death.get("description")}
        _append_nav(mech_nav, mech_seen, target=death.get("deathSection"), kind="death", outcome="death", params=params)

    # Merge choice text into mechanics and drop overlapping choice targets
    choice_text_by_target = {}
    for entry in choice_nav:
        if entry.get("targetSection") and entry.get("choiceText"):
            choice_text_by_target.setdefault(entry["targetSection"], entry["choiceText"])

    mech_targets = {e.get("targetSection") for e in mech_nav if e.get("targetSection")}
    for entry in mech_nav:
        tgt = entry.get("targetSection")
        if tgt and not entry.get("choiceText") and tgt in choice_text_by_target:
            entry["choiceText"] = choice_text_by_target[tgt]

    filtered_choices = [e for e in choice_nav if e.get("targetSection") not in mech_targets]
    return filtered_choices + mech_nav


def classify_type(section_id: str, portion: Dict[str, Any], text_body: str) -> str:
    allowed_types = {
        "section",
        "front_cover",
        "back_cover",
        "title_page",
        "publishing_info",
        "toc",
        "intro",
        "rules",
        "adventure_sheet",
        "template",
        "background",
    }
    if portion.get("section_type") in allowed_types:
        return portion["section_type"]
    if portion.get("type") in allowed_types:
        return portion["type"]
    if section_id.isdigit():
        return "section"
    if section_id.lower() == "background":
        return "intro"

    lower = (text_body or "").lower()
    if "table of contents" in lower or "contents" in lower:
        return "toc"
    if "introduction" in lower or lower.startswith("introduction") or "story so far" in lower:
        return "intro"
    if ("rules" in lower or "how to play" in lower or "how to fight" in lower or
            "rules of the game" in lower or "how to use this book" in lower):
        return "rules"
    if "adventure sheet" in lower or "character sheet" in lower or "equipment" in lower or "possessions" in lower:
        return "adventure_sheet"
    if "published" in lower or "isbn" in lower:
        return "publishing_info"
    return "template"


def is_gameplay(section_id: str, portion: Dict[str, Any], candidate_type: Optional[str] = None) -> bool:
    if portion.get("is_gameplay") is not None:
        return bool(portion["is_gameplay"])
    if candidate_type == "section" or section_id.isdigit():
        return True
    if section_id.lower() == "background":
        return True
    if portion.get("choices") or portion.get("combat") or portion.get("test_luck") or portion.get("item_effects"):
        return True
    return False


def build_section(portion: Dict[str, Any], emit_text: bool, emit_provenance_text: bool) -> tuple[str, Dict[str, Any]]:
    """
    Build a Fighting Fantasy Engine section from an EnrichedPortion.

    Simplified for AI-first pipeline - raw_text is always provided by portionize_ai_extract_v1.
    """
    section_id = str(portion.get("section_id") or portion.get("portion_id"))
    page_start = int(portion.get("page_start"))
    page_end = int(portion.get("page_end"))
    page_start_original = portion.get("page_start_original")
    page_end_original = portion.get("page_end_original")

    html_body = portion.get("raw_html", "")
    text_body = portion.get("raw_text") or html_to_text(html_body)
    raw_body = text_body

    navigation = make_navigation(portion)
    if not navigation and section_id.lower() == "background":
        navigation = [{
            "targetSection": "1",
            "kind": "choice",
            "choiceText": "Turn to 1",
        }]

    candidate_type = classify_type(section_id, portion, text_body)

    section: Dict[str, Any] = {
        "id": section_id,
        "html": html_body,
        "pageStart": page_start,
        "pageEnd": page_end,
        "isGameplaySection": is_gameplay(section_id, portion, candidate_type),
        "type": candidate_type,
    }
    # Omit plain text fields from final gamebook output.

    if navigation:
        section["navigation"] = navigation

    # Propagate end_game marker (used to suppress no-choice warnings)
    if portion.get("end_game") or portion.get("endGame") or portion.get("is_endgame"):
        section["end_game"] = True
    ending_status = portion.get("ending")
    if ending_status in ("death", "victory", "defeat"):
        section["status"] = ending_status

    # Optional fields if present
    if portion.get("items"):
        # Strip navigation targets from item checks; navigation is canonical.
        sanitized_items = []
        for item in portion["items"]:
            if not isinstance(item, dict):
                continue
            cleaned = dict(item)
            cleaned.pop("checkSuccessSection", None)
            cleaned.pop("checkFailureSection", None)
            sanitized_items.append(cleaned)
        if sanitized_items:
            section["items"] = sanitized_items
    if portion.get("stat_modifications"):
        section["statModifications"] = portion["stat_modifications"]
    # testYourLuck targets are encoded in navigation; omit to avoid duplication.
    if portion.get("deathConditions"):
        sanitized_deaths = []
        for death in portion["deathConditions"]:
            if not isinstance(death, dict):
                continue
            cleaned = dict(death)
            cleaned.pop("deathSection", None)
            sanitized_deaths.append(cleaned)
        if sanitized_deaths:
            section["deathConditions"] = sanitized_deaths
    combat = portion.get("combat")
    combat_list = [combat] if isinstance(combat, dict) else (combat or [])
    section_combat = []
    for c in combat_list:
        if not isinstance(c, dict):
            continue
        if c.get("skill") is None or c.get("stamina") is None:
            continue
        enemy = {
            "enemy": c.get("name") or c.get("enemy") or "Creature",
            "skill": c.get("skill"),
            "stamina": c.get("stamina"),
        }
        if c.get("specialRules"):
            enemy["special_rules"] = c.get("specialRules")
        if c.get("allowEscape") is not None:
            enemy["allow_escape"] = c.get("allowEscape")
        section_combat.append(enemy)
    if section_combat:
        section["combat"] = section_combat

    provenance = {
        "portion_id": portion.get("portion_id"),
        "orig_portion_id": portion.get("orig_portion_id"),
        "confidence": portion.get("confidence"),
        "continuation_of": portion.get("continuation_of"),
        "continuation_confidence": portion.get("continuation_confidence"),
        "source_images": portion.get("source_images") or [],
        "source_pages": list(range(page_start, page_end + 1)),
        "source_pages_original": list(range(page_start_original, page_end_original + 1)) if isinstance(page_start_original, int) and isinstance(page_end_original, int) else None,
        "macro_section": portion.get("macro_section"),
        "module_id": portion.get("module_id"),
        "run_id": portion.get("run_id"),
    }
    # Omit raw/clean text in provenance for final gamebook output.
    section["provenance"] = provenance
    return section_id, section


def collect_targets(section: Dict[str, Any]) -> List[str]:
    targets: List[str] = []
    for nav in section.get("navigation") or []:
        if nav.get("targetSection"):
            targets.append(str(nav["targetSection"]))
    return targets


def main():
    parser = argparse.ArgumentParser(description="Build Fighting Fantasy Engine gamebook JSON from enriched portions.")
    parser.add_argument("--portions", required=True, help="Path to portions_enriched.jsonl")
    parser.add_argument("--out", required=True, help="Output gamebook JSON path")
    parser.add_argument("--title", required=True, help="Gamebook title")
    parser.add_argument("--author", help="Gamebook author")
    parser.add_argument("--start-section", "--start_section", default="1", dest="start_section", help="Starting section id")
    parser.add_argument("--format-version", "--format_version", default="1.0.0", dest="format_version", help="Format version string")
    parser.add_argument("--allow-stubs", action="store_true", dest="allow_stubs",
                        help="Permit stub backfill for missing targets (default: fail if stubs needed)")
    parser.add_argument("--expected-range", "--expected_range", default="1-400", dest="expected_range",
                        help="Expected section id range (e.g., 1-400). Targets outside are ignored.")
    parser.add_argument("--emit-text", "--emit_text", dest="emit_text", action="store_true",
                        help="Include plain text in section outputs (default: true)")
    parser.add_argument("--drop-text", "--drop_text", dest="emit_text", action="store_false",
                        help="Omit plain text from section outputs")
    parser.set_defaults(emit_text=True)
    parser.add_argument("--emit-provenance-text", "--emit_provenance_text", dest="emit_provenance_text",
                        action="store_true", help="Include raw/clean text in provenance (default: true)")
    parser.add_argument("--drop-provenance-text", "--drop_provenance_text", dest="emit_provenance_text",
                        action="store_false", help="Omit raw/clean text from provenance")
    parser.set_defaults(emit_provenance_text=True)
    parser.add_argument("--unresolved-missing", "--unresolved_missing", dest="unresolved_missing",
                        help="Optional path to unresolved_missing.json (sections verified missing from source).")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    parser.add_argument("--pages", help="(ignored; driver compatibility)")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("build_ff_engine", "running", current=0, total=None, message="Loading enriched portions", module_id="build_ff_engine_v1")

    # Parse expected range for filtering targets/stubs.
    try:
        r0, r1 = args.expected_range.split("-", 1)
        min_expected = int(r0.strip())
        max_expected = int(r1.strip())
    except Exception:
        min_expected, max_expected = 1, 400

    # Load unresolved-missing allowlist (explicit artifact). If present, we can allow stubs
    # for these missing IDs without requiring --allow-stubs.
    unresolved_allow: set[str] = set()
    unresolved_path = args.unresolved_missing
    if not unresolved_path:
        unresolved_path = os.path.join(os.path.dirname(os.path.abspath(args.out)), "unresolved_missing.json")
    try:
        if unresolved_path and os.path.exists(unresolved_path):
            with open(unresolved_path, "r", encoding="utf-8") as f:
                unresolved_allow = {str(x) for x in json.load(f)}
    except Exception:
        unresolved_allow = set()

    portions = list(read_jsonl(args.portions))

    sections: Dict[str, Any] = {}
    for idx, portion in enumerate(portions, start=1):
        # Skip error records
        if "error" in portion:
            continue

        section_id, section = build_section(portion, args.emit_text, args.emit_provenance_text)
        sections[section_id] = section
        if idx % 20 == 0:
            logger.log("build_ff_engine", "running", current=idx, total=len(portions),
                       message=f"Assembled {idx}/{len(portions)} sections", module_id="build_ff_engine_v1")

    # Backfill any missing target sections with stubs to satisfy validator
    all_targets: List[str] = []
    for sec in sections.values():
        all_targets.extend(collect_targets(sec))
    # Ignore targets outside expected range (often OCR/AI noise in provenance targets).
    missing = {
        t for t in all_targets
        if t.isdigit()
        and min_expected <= int(t) <= max_expected
        and t not in sections
    }
    stub_targets = sorted(missing, key=lambda x: int(x))
    stub_count = len(stub_targets)

    allow_stubs_effective = args.allow_stubs or (stub_targets and all(t in unresolved_allow for t in stub_targets))

    if stub_count and not allow_stubs_effective:
        # Explicit failure message for observability
        missing_ids_preview = ", ".join(stub_targets[:10])
        if stub_count > 10:
            missing_ids_preview += f" (and {stub_count - 10} more)"
        
        error_msg = (
            f"\n❌ BUILD FAILED: {stub_count} sections require stub backfill\n\n"
            f"Missing section IDs: {missing_ids_preview}\n\n"
            f"Root cause: Pipeline detected section boundaries but extraction failed, "
            f"or boundaries are missing entirely for these sections.\n\n"
            f"Next steps:\n"
            f"  1. Check boundary detection: Are these sections in section_boundaries_merged.jsonl?\n"
            f"  2. Check extraction: Did portionize_ai_extract_v1 fail on these boundaries?\n"
            f"  3. For debugging: Use --allow-stubs to build with placeholders and inspect validation_report.json\n"
            f"  4. To fix: Improve boundary detection (Priority 1) or extraction quality (Priority 2)\n"
        )
        
        logger.log("build_ff_engine", "failed", current=len(portions), total=len(portions),
                   message=f"Stub backfill required ({stub_count}); failing per policy", module_id="build_ff_engine_v1")
        raise SystemExit(error_msg)

    for mid in sorted(missing, key=lambda x: int(x) if str(x).isdigit() else x):
        reason = "backfilled missing target"
        if mid in unresolved_allow:
            reason = "verified_missing_from_source"
        stub_section = {
            "id": mid,
            "html": "",
            "isGameplaySection": True,
            "type": "section",
            "provenance": {"stub": True, "reason": reason},
        }
        sections[mid] = stub_section

    start_section = str(args.start_section)
    if "background" in sections:
        start_section = "background"
    if start_section not in sections and sections:
        # prefer numeric "1" if present, else first section id
        if "1" in sections:
            start_section = "1"
        else:
            start_section = sorted(sections.keys())[0]

    gamebook = {
        "metadata": {
            "title": args.title,
            "author": args.author,
            "startSection": start_section,
            "formatVersion": args.format_version,
        },
        "sections": sections,
        "provenance": {
            "stub_targets": stub_targets[:20],
            "stub_count": stub_count,
            "stubs_allowed": bool(allow_stubs_effective),
            "expected_range": args.expected_range,
            "unresolved_missing": sorted(
                [s for s in unresolved_allow if s.isdigit()],
                key=lambda x: int(x),
            )
            if unresolved_allow
            else [],
        },
    }

    save_json(args.out, gamebook)
    msg = f"Wrote {len(sections)} sections → {args.out}"
    if stub_count:
        msg += f" (stubs added: {stub_count})"
    logger.log("build_ff_engine", "done", current=len(portions), total=len(portions),
               message=msg, artifact=args.out,
               module_id="build_ff_engine_v1", schema_version="ff_engine_gamebook_v1",
               extra={"summary_metrics": {"sections_count": len(sections), "stubs_count": stub_count}})
    print(f"Wrote gamebook with {len(sections)} sections to {args.out}")


if __name__ == "__main__":
    main()
