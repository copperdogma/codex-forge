#!/usr/bin/env python3
import argparse
import json
import re
from typing import Any, Dict, List, Optional

from modules.common.utils import read_jsonl, save_json
from modules.common.combat_styles import COMBAT_STYLE_DEFS
from modules.common.html_utils import html_to_text

try:
    from modules.common.openai_client import OpenAI
except ImportError:
    OpenAI = None


KEYWORDS = (
    "combat",
    "fighting",
    "attack strength",
    "skill",
    "stamina",
    "armour",
    "armor",
    "firepower",
    "shooting",
    "hand fighting",
    "hand-to-hand",
)


def _page_has_section_header(html: str) -> bool:
    if not html:
        return False
    if re.search(r"<h2>\\s*\\d+\\s*</h2>", html, re.IGNORECASE):
        return True
    return False


def _normalize_style_id(raw: str) -> str:
    if not raw:
        return ""
    clean = re.sub(r"[^a-z0-9_-]+", "_", raw.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean


def _extract_frontmatter_pages(pages: List[Dict[str, Any]], max_pages: int) -> List[Dict[str, Any]]:
    first_section_page = None
    for page in pages:
        html = page.get("html") or page.get("raw_html") or ""
        if _page_has_section_header(html):
            first_section_page = page.get("page_number") or page.get("page") or None
            break
    if first_section_page is None:
        return pages[:max_pages]
    front = [p for p in pages if (p.get("page_number") or p.get("page")) < first_section_page]
    return front[:max_pages]


def _frontmatter_text(pages: List[Dict[str, Any]]) -> str:
    chunks = []
    for page in pages:
        html = page.get("html") or page.get("raw_html") or ""
        text = html_to_text(html) or ""
        if not text:
            continue
        if any(k in text.lower() for k in KEYWORDS):
            chunks.append(text.strip())
    if not chunks:
        chunks = [html_to_text(p.get("html") or p.get("raw_html") or "") for p in pages]
    return "\n\n".join([c for c in chunks if c]).strip()


def _parse_styles(raw: Any) -> Dict[str, Dict[str, Any]]:
    styles: Dict[str, Dict[str, Any]] = {}
    if isinstance(raw, dict):
        if "styles" in raw and isinstance(raw["styles"], dict):
            styles = raw["styles"]
        elif "styles" in raw and isinstance(raw["styles"], list):
            for entry in raw["styles"]:
                if isinstance(entry, dict):
                    sid = _normalize_style_id(entry.get("id") or entry.get("name") or "")
                    if sid:
                        styles[sid] = entry
        else:
            # assume raw is already a map of id->def
            styles = {str(k): v for k, v in raw.items() if isinstance(v, dict)}
    elif isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict):
                sid = _normalize_style_id(entry.get("id") or entry.get("name") or "")
                if sid:
                    styles[sid] = entry
    normalized: Dict[str, Dict[str, Any]] = {}
    for sid, style in styles.items():
        if not isinstance(style, dict):
            continue
        norm_id = _normalize_style_id(style.get("id") or sid)
        if not norm_id:
            continue
        style["id"] = norm_id
        primary = style.get("primaryStat")
        health = style.get("healthStat")
        if isinstance(primary, str):
            style["primaryStat"] = primary.strip().lower()
        if isinstance(health, str):
            style["healthStat"] = health.strip().lower()
        keywords = style.get("keywords")
        if isinstance(keywords, list):
            style["keywords"] = [str(k).strip().lower() for k in keywords if str(k).strip()]
        normalized[norm_id] = style
    if normalized and not any(s.get("default") for s in normalized.values()):
        for style in normalized.values():
            if style.get("primaryStat") == "skill" and style.get("healthStat") == "stamina":
                style["default"] = True
                break
    return normalized


def _extract_styles_with_ai(client, model: str, text: str) -> Dict[str, Dict[str, Any]]:
    prompt = f"""You are extracting combat rules from the frontmatter of a Fighting Fantasy gamebook.
Return JSON only.

From the text below, identify each distinct combat style and output a JSON object with:
- styles: an array of style objects with fields:
  - id: short lowercase slug (e.g., standard, robot, vehicle, shooting, hand)
  - name
  - primaryStat: one of skill, firepower
  - healthStat: one of stamina, armour
  - attackStrength: {{attacker: \"...\", defender: \"...\"}}
  - damage: {{stat: \"stamina\"|\"armour\", amount: \"...\"}}
  - endCondition: {{stat: \"stamina\"|\"armour\", threshold: number}}
  - escape: optional, with requires + damage if described
  - keywords: list of words/phrases useful to match this style in sections
  - default: true for the general/default combat style (if applicable)

Text:
\"\"\"\n{text}\n\"\"\"\n"""
    resp = client.responses.create(
        model=model,
        input=prompt,
        temperature=0,
    )
    content = resp.output_text
    try:
        data = json.loads(content)
        return _parse_styles(data)
    except Exception:
        pass
    # Fallback: attempt to extract JSON from markdown/code fences.
    match = re.search(r"\\{.*\\}", content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return _parse_styles(data)
        except Exception:
            return {}
    return {}


def _default_attack_strength(primary: str) -> Dict[str, str]:
    if primary == "firepower":
        return {"attacker": "2d6 + FIREPOWER", "defender": "2d6 + ENEMY_FIREPOWER"}
    return {"attacker": "2d6 + SKILL", "defender": "2d6 + ENEMY_SKILL"}


def _default_damage_amount(text: str, health: str) -> Any:
    lower = text.lower()
    if "1d6" in lower or "one die" in lower:
        return "1d6"
    return 2 if health in {"stamina", "armour"} else 2


def _fallback_styles_from_text(text: str) -> Dict[str, Dict[str, Any]]:
    styles: Dict[str, Dict[str, Any]] = {}
    lower = text.lower()
    headings = [
        ("individual combat", "standard"),
        ("standard combat", "standard"),
        ("robot combat", "robot"),
        ("vehicle combat", "vehicle"),
        ("hand fighting", "hand"),
        ("shooting", "shooting"),
    ]
    for label, sid in headings:
        if label in lower:
            styles[sid] = {
                "id": sid,
                "name": label.title(),
                "primaryStat": "skill",
                "healthStat": "stamina",
                "keywords": [label],
            }
    if "robot combat" in lower:
        styles["robot"] = {
            "id": "robot",
            "name": "Robot Combat",
            "primaryStat": "skill",
            "healthStat": "armour",
            "keywords": ["robot", "armour", "speed", "combat bonus"],
        }
    if "vehicle combat" in lower or "firepower" in lower:
        styles["vehicle"] = {
            "id": "vehicle",
            "name": "Vehicle Combat",
            "primaryStat": "firepower",
            "healthStat": "armour",
            "keywords": ["vehicle", "firepower", "armour"],
        }
    for style in styles.values():
        primary = style.get("primaryStat") or "skill"
        health = style.get("healthStat") or "stamina"
        style["primaryStat"] = primary
        style["healthStat"] = health
        style.setdefault("attackStrength", _default_attack_strength(primary))
        style.setdefault("damage", {"stat": health, "amount": _default_damage_amount(text, health)})
        style.setdefault("endCondition", {"stat": health, "threshold": 0})
    if styles and not any(s.get("default") for s in styles.values()) and "standard" in styles:
        styles["standard"]["default"] = True
    return styles


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract combat styles from frontmatter text.")
    parser.add_argument("--pages", required=True, help="Input pages HTML JSONL")
    parser.add_argument("--portions", required=True, help="Input portions JSONL (unused)")
    parser.add_argument("--out", required=True, help="Output JSON")
    parser.add_argument("--model", default="gpt-5.1", help="Model to use")
    parser.add_argument("--styles", default="", help="Comma-separated style ids to emit (static)")
    parser.add_argument("--styles-file", dest="styles_file", default="", help="Static combat styles JSON file")
    parser.add_argument("--max_pages", "--max-pages", dest="max_pages", type=int, default=8)
    parser.add_argument("--use-ai", action="store_true", default=True)
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    pages = list(read_jsonl(args.pages))
    front_pages = _extract_frontmatter_pages(pages, args.max_pages)
    text = _frontmatter_text(front_pages)
    styles: Dict[str, Dict[str, Any]] = {}
    source = "frontmatter"

    if args.styles_file:
        try:
            with open(args.styles_file, "r", encoding="utf-8") as f:
                styles = _parse_styles(json.load(f))
                source = "styles_file"
        except Exception:
            styles = {}

    if not styles and args.styles:
        wanted = [s.strip().lower() for s in args.styles.split(",") if s.strip()]
        for sid in wanted:
            if sid in COMBAT_STYLE_DEFS:
                styles[sid] = dict(COMBAT_STYLE_DEFS[sid])
        source = "static"

    ai_used = False
    if not styles and args.use_ai and OpenAI and text:
        try:
            client = OpenAI()
            styles = _extract_styles_with_ai(client, args.model, text)
            ai_used = True
        except Exception:
            styles = {}

    if not styles and text:
        styles = _fallback_styles_from_text(text)

    result = {
        "schema_version": "combat_styles_v1",
        "source_pages": [p.get("page_number") or p.get("page") for p in front_pages],
        "styles": styles,
        "debug": {
            "ai_used": ai_used,
            "text_len": len(text or ""),
            "source": source,
        },
    }
    save_json(args.out, result)


if __name__ == "__main__":
    main()
