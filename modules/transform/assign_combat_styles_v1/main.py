#!/usr/bin/env python3
import argparse
import json
from typing import Any, Dict, List, Optional, Tuple

from modules.common.utils import read_jsonl, save_jsonl
from modules.common.html_utils import html_to_text


def _load_styles(path: str) -> Dict[str, Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    styles = data.get("styles") if isinstance(data, dict) else None
    if isinstance(styles, dict):
        return {str(k): v for k, v in styles.items() if isinstance(v, dict)}
    if isinstance(data, dict):
        return {str(k): v for k, v in data.items() if isinstance(v, dict)}
    return {}


def _infer_stats(enemies: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    primary = None
    health = None
    for e in enemies:
        if e.get("firepower") is not None:
            primary = "firepower"
        if e.get("skill") is not None and primary is None:
            primary = "skill"
        if e.get("armour") is not None:
            health = "armour"
        if e.get("stamina") is not None and health is None:
            health = "stamina"
    return primary, health


def _score_keywords(style: Dict[str, Any], text: str) -> int:
    keywords = style.get("keywords") or []
    if not isinstance(keywords, list):
        return 0
    lower = text.lower()
    score = 0
    for kw in keywords:
        if not kw:
            continue
        if str(kw).lower() in lower:
            score += 1
    return score


def _pick_style(styles: Dict[str, Dict[str, Any]], primary: Optional[str], health: Optional[str], text: str) -> Optional[str]:
    if not styles:
        return None
    lower = text.lower()
    if "shooting combat" in lower and "shooting" in styles:
        return "shooting"
    if ("hand fighting" in lower or "hand-to-hand" in lower) and "hand" in styles:
        return "hand"
    if "vehicle combat" in lower and "vehicle" in styles:
        return "vehicle"
    candidates = []
    for sid, style in styles.items():
        if not isinstance(style, dict):
            continue
        p = style.get("primaryStat")
        h = style.get("healthStat")
        if p and primary and p != primary:
            continue
        if h and health and h != health:
            continue
        candidates.append((sid, style))
    if not candidates:
        return None
    best_id = None
    best_score = -1
    for sid, style in candidates:
        score = _score_keywords(style, text)
        if score > best_score:
            best_score = score
            best_id = sid
    if best_score <= 0:
        for sid, style in candidates:
            if style.get("default"):
                return sid
        return candidates[0][0]
    return best_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign combat styles using frontmatter definitions.")
    parser.add_argument("--input", required=True, help="Input portions JSONL")
    parser.add_argument("--styles", required=True, help="Combat styles JSON")
    parser.add_argument("--out", required=True, help="Output portions JSONL")
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    styles = _load_styles(args.styles)
    portions = list(read_jsonl(args.input))
    updated = []

    for portion in portions:
        combats = portion.get("combat") or []
        if not isinstance(combats, list):
            combats = [combats]
        if combats:
            text = html_to_text(portion.get("raw_html") or "") or ""
            for combat in combats:
                if not isinstance(combat, dict):
                    continue
                existing = combat.get("style")
                if isinstance(existing, str) and existing in styles:
                    # Respect an explicit style already assigned upstream (e.g., extract_combat_v1).
                    continue
                enemies = combat.get("enemies") or []
                if not isinstance(enemies, list) or not enemies:
                    continue
                primary, health = _infer_stats(enemies)
                style_id = _pick_style(styles, primary, health, text)
                if style_id:
                    combat["style"] = style_id
        portion["combat"] = combats
        updated.append(portion)

    save_jsonl(args.out, updated)


if __name__ == "__main__":
    main()
