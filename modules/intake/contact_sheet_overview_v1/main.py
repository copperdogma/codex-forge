import argparse
import json
from pathlib import Path
from typing import List
import base64
from modules.common.utils import read_jsonl, ensure_dir, save_jsonl
from modules.common.openai_client import OpenAI
def parse_json_relaxed(text: str):
    try:
        return json.loads(text)
    except Exception:
        pass
    # try to extract JSON substring
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return None
    return None


def summarize_manifest(manifest_path: Path):
    sheets = {}
    tiles = list(read_jsonl(manifest_path))
    for t in tiles:
        sheets.setdefault(t["sheet_id"], 0)
        sheets[t["sheet_id"]] += 1
    display_order = [t.get("display_number") for t in tiles if t.get("tile_index") == 0]
    return {
        "sheet_count": len(sheets),
        "tile_count": len(tiles),
        "sheets": list(sheets.keys()),
        "display_order": display_order,
        "tile_map": [
            {
                "display_number": t.get("display_number"),
                "source_image": t.get("source_image"),
                "sheet_id": t.get("sheet_id"),
                "tile_index": t.get("tile_index"),
            }
            for t in tiles
        ],
    }


def encode_image(p: Path) -> str:
    mime = "image/jpeg" if p.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def prompt_overview_per_sheet(client: OpenAI, sheet_img: Path, tile_map: List[dict], model: str, vision_detail: str) -> dict:
    sheet_tiles = [t for t in tile_map if t.get("sheet_id") == sheet_img.stem]
    mapping_text = json.dumps(sheet_tiles)
    image_part = {
        "type": "image_url",
        "image_url": {"url": encode_image(sheet_img), "detail": vision_detail},
    }
    system_prompt = (
        "Classify pages in this one contact sheet."
        " Use the tile_map (display_number->filename) to reference pages."
        " Return JSON with keys: signals (list), signal_evidence (array of {signal, pages, reason}), warnings (list)."
        " Signals: tables, formulas, images, cyoa, maps, sheet_music, forms, comics."
        " Mark 'tables' only when clear rows/columns exist; skip photos/prose."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [{"type": "text", "text": f"tile_map: {mapping_text}"}, image_part]},
    ]
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0,
        max_tokens=200,
    )
    raw = resp.choices[0].message.content
    data = parse_json_relaxed(raw) or {"signals": [], "signal_evidence": [], "warnings": ["LLM parse failure"]}
    data.setdefault("signals", [])
    data.setdefault("signal_evidence", [])
    data.setdefault("warnings", [])
    return data


def merge_sheet_results(results: List[dict]) -> dict:
    signals = []
    evidence = []
    warnings = []
    for r in results:
        signals.extend(r.get("signals", []))
        evidence.extend(r.get("signal_evidence", []))
        warnings.extend(r.get("warnings", []))
    signals = list(dict.fromkeys(signals))
    # merge evidence by signal
    merged = {}
    for ev in evidence:
        sig = ev.get("signal")
        if not sig:
            continue
        merged.setdefault(sig, {"signal": sig, "pages": [], "reason": ""})
        merged[sig]["pages"].extend(ev.get("pages", []))
        if ev.get("reason"):
            merged[sig]["reason"] = ev.get("reason")
    for m in merged.values():
        # normalize to strings for schema validation
        m["pages"] = sorted({str(p) for p in m["pages"]})
    return {
        "signals": signals,
        "signal_evidence": list(merged.values()),
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description="Overview classifier from contact sheets (stub)")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--sheets_dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--max_sheets", type=int, default=0)
    parser.add_argument("--vision_detail", default="low", choices=["low", "high"])
    parser.add_argument("--mock_output", default=None, help="Path to JSON to use instead of LLM")
    parser.add_argument("--boost_model", default=None)
    args, _unknown = parser.parse_known_args()

    ensure_dir(Path(args.out).parent)
    summary = summarize_manifest(Path(args.manifest))
    sheet_paths = sorted(Path(args.sheets_dir).glob("sheet-*.jpg"))
    if args.mock_output:
        llm_plan = json.load(open(args.mock_output, "r", encoding="utf-8"))
    else:
        client = OpenAI()
        selected_sheets = sheet_paths if args.max_sheets <= 0 else sheet_paths[: args.max_sheets]
        per_sheet = []
        for p in selected_sheets:
            per_sheet.append(
                prompt_overview_per_sheet(client, p, summary.get("tile_map", []), args.model, args.vision_detail)
            )
        merged = merge_sheet_results(per_sheet)
        llm_plan = {
            "book_type": None,  # leave for downstream planner
            "type_confidence": None,
            **merged,
            "zoom_requests": [],
        }

    plan = {
        "schema_version": "intake_plan_v1",
        "book_type": llm_plan.get("book_type") or "mixed",
        "type_confidence": llm_plan.get("type_confidence", 0.3),
        "sections": [],
        "zoom_requests": llm_plan.get("zoom_requests", []),
        "recommended_recipe": None,
        "sectioning_strategy": "contact-sheet overview",
        "assumptions": ["No web lookup; vision from contact sheets"],
        "warnings": llm_plan.get("warnings", []),
        "signals": llm_plan.get("signals", []),
        "signal_evidence": [
            {
                **ev,
                "pages": [str(p) for p in ev.get("pages", [])],
            }
            for ev in llm_plan.get("signal_evidence", [])
        ],
        "sheets": summary.get("sheets", []),
        "manifest_path": str(Path(args.manifest)),
        "meta": {"summary": summary, "model": args.model},
    }
    save_jsonl(args.out, [plan])
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
