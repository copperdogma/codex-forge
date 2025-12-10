import argparse
import json
from typing import Any, Dict, List, Optional

from modules.common.utils import read_jsonl, save_json, ProgressLogger


def make_navigation(portion: Dict[str, Any]) -> List[Dict[str, Any]]:
    nav: List[Dict[str, Any]] = []
    for choice in portion.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        tgt = choice.get("target")
        if tgt is None:
            continue
        nav.append({
            "targetSection": str(tgt),
            "choiceText": choice.get("text"),
            "isConditional": False,
        })
    if not nav:
        # Fall back to targets list if present
        for tgt in portion.get("targets") or []:
            nav.append({"targetSection": str(tgt), "isConditional": False})
    return nav


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
    }
    if portion.get("section_type") in allowed_types:
        return portion["section_type"]
    if portion.get("type") in allowed_types:
        return portion["type"]
    if section_id.isdigit():
        return "section"

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
    if portion.get("choices") or portion.get("combat") or portion.get("test_luck") or portion.get("item_effects"):
        return True
    return False


def build_section(portion: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    """
    Build a Fighting Fantasy Engine section from an EnrichedPortion.

    Simplified for AI-first pipeline - raw_text is always provided by portionize_ai_extract_v1.
    """
    section_id = str(portion.get("section_id") or portion.get("portion_id"))
    page_start = int(portion.get("page_start"))
    page_end = int(portion.get("page_end"))

    # AI pipeline always provides raw_text
    text_body = portion.get("raw_text", "")
    raw_body = text_body

    nav_links = make_navigation(portion)

    candidate_type = classify_type(section_id, portion, text_body)

    section: Dict[str, Any] = {
        "id": section_id,
        "text": text_body,
        "pageStart": page_start,
        "pageEnd": page_end,
        "isGameplaySection": is_gameplay(section_id, portion, candidate_type),
        "type": candidate_type,
    }

    if nav_links:
        section["navigationLinks"] = nav_links

    # Propagate end_game marker (used to suppress no-choice warnings)
    if portion.get("end_game") or portion.get("endGame") or portion.get("is_endgame"):
        section["end_game"] = True

    # Optional fields if present
    if portion.get("items"):
        section["items"] = portion["items"]
    if portion.get("stat_modifications"):
        section["statModifications"] = portion["stat_modifications"]
    if portion.get("testYourLuck"):
        section["testYourLuck"] = portion["testYourLuck"]
    if portion.get("deathConditions"):
        section["deathConditions"] = portion["deathConditions"]
    combat = portion.get("combat")
    if combat and isinstance(combat, dict) and combat.get("skill") is not None and combat.get("stamina") is not None:
        creature = {
            "name": combat.get("name") or "Creature",
            "skill": combat.get("skill"),
            "stamina": combat.get("stamina"),
        }
        if combat.get("specialRules"):
            creature["specialRules"] = combat["specialRules"]
        if combat.get("allowEscape") is not None:
            creature["allowEscape"] = combat["allowEscape"]
        if combat.get("escapeSection"):
            creature["escapeSection"] = str(combat["escapeSection"])
        # Only include combat if we have a winSection to satisfy schema; otherwise keep in provenance
        if combat.get("winSection"):
            section["combat"] = {
                "creature": creature,
                "winSection": str(combat["winSection"]),
            }
            if combat.get("loseSection"):
                section["combat"]["loseSection"] = str(combat["loseSection"])

    provenance = {
        "portion_id": portion.get("portion_id"),
        "orig_portion_id": portion.get("orig_portion_id"),
        "confidence": portion.get("confidence"),
        "continuation_of": portion.get("continuation_of"),
        "continuation_confidence": portion.get("continuation_confidence"),
        "source_images": portion.get("source_images") or [],
        "source_pages": list(range(page_start, page_end + 1)),
        "raw_text": raw_body,
        "clean_text": text_body,
        "module_id": portion.get("module_id"),
        "run_id": portion.get("run_id"),
    }
    section["provenance"] = provenance
    return section_id, section


def collect_targets(section: Dict[str, Any]) -> List[str]:
    targets: List[str] = []
    for nav in section.get("navigationLinks") or []:
        if nav.get("targetSection"):
            targets.append(str(nav["targetSection"]))
    for cond in section.get("conditionalNavigation") or []:
        for key in ("ifTrue", "ifFalse"):
            link = cond.get(key) or {}
            tgt = link.get("targetSection")
            if tgt:
                targets.append(str(tgt))
    combat = section.get("combat") or {}
    for key in ("winSection", "loseSection"):
        tgt = combat.get(key)
        if tgt:
            targets.append(str(tgt))
    for ty in section.get("testYourLuck") or []:
        for key in ("luckySection", "unluckySection"):
            tgt = ty.get(key)
            if tgt:
                targets.append(str(tgt))
    for item in section.get("items") or []:
        for key in ("checkSuccessSection", "checkFailureSection"):
            tgt = item.get(key)
            if tgt:
                targets.append(str(tgt))
    for death in section.get("deathConditions") or []:
        tgt = death.get("deathSection")
        if tgt:
            targets.append(str(tgt))
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
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    parser.add_argument("--pages", help="(ignored; driver compatibility)")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("build_ff_engine", "running", current=0, total=None, message="Loading enriched portions", module_id="build_ff_engine_v1")

    portions = list(read_jsonl(args.portions))

    sections: Dict[str, Any] = {}
    for idx, portion in enumerate(portions, start=1):
        # Skip error records
        if "error" in portion:
            continue

        section_id, section = build_section(portion)
        sections[section_id] = section
        if idx % 20 == 0:
            logger.log("build_ff_engine", "running", current=idx, total=len(portions),
                       message=f"Assembled {idx}/{len(portions)} sections", module_id="build_ff_engine_v1")

    # Backfill any missing target sections with stubs to satisfy validator
    all_targets: List[str] = []
    for sec in sections.values():
        all_targets.extend(collect_targets(sec))
    missing = {t for t in all_targets if t.isdigit() and t not in sections}
    stub_targets = sorted(missing, key=lambda x: int(x))
    stub_count = len(stub_targets)

    if stub_count and not args.allow_stubs:
        logger.log("build_ff_engine", "failed", current=len(portions), total=len(portions),
                   message=f"Stub backfill required ({stub_count}); failing per policy", module_id="build_ff_engine_v1")
        raise SystemExit(f"Stub backfill required ({stub_count}); rerun after fixing upstream coverage or pass --allow-stubs")

    for mid in sorted(missing, key=lambda x: int(x) if str(x).isdigit() else x):
        sections[mid] = {
            "id": mid,
            "text": "",
            "isGameplaySection": True,
            "type": "section",
            "provenance": {"stub": True, "reason": "backfilled missing target"},
        }

    start_section = str(args.start_section)
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
            "stubs_allowed": bool(args.allow_stubs),
        },
    }

    save_json(args.out, gamebook)
    msg = f"Wrote {len(sections)} sections → {args.out}"
    if stub_count:
        msg += f" (stubs added: {stub_count})"
    logger.log("build_ff_engine", "done", current=len(portions), total=len(portions),
               message=msg, artifact=args.out,
               module_id="build_ff_engine_v1", schema_version="ff_engine_gamebook_v1",
               extra={"stub_count": stub_count})
    print(f"Wrote gamebook with {len(sections)} sections to {args.out}")


if __name__ == "__main__":
    main()
