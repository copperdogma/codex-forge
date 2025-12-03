import argparse
import json
import os
import re
from typing import List, Dict, Any

from openai import OpenAI

from modules.common.utils import ProgressLogger, read_jsonl, ensure_dir, append_jsonl
from schemas import PortionHypothesis

SYSTEM_PROMPT = """You are detecting gameplay section headers inside the GAME region of a Fighting Fantasy book.
- Sections are numbered 1-400. A real header is a standalone number at start of text.
- Ignore page numbers or ranges; ignore anything outside GAME.
Return JSON only: {"sections": [{"section_id": "123", "page": int, "line": int|null, "confidence": 0-1}]}.
Be precise; if unsure, omit."""


PAGE_RE = re.compile(r"^\s*\d{1,3}[–-]\d{1,3}\s*")


def clean_lines(text: str) -> List[str]:
    lines = []
    for line in (text or "").splitlines():
        line = PAGE_RE.sub("", line).strip()
        if line:
            lines.append(line)
    return lines


def format_window(batch: List[Dict[str, Any]]):
    content = []
    for p in batch:
        lines = clean_lines(p.get("clean_text") or p.get("raw_text") or "")
        snippet = "\n".join([f"{i}:{l}" for i, l in enumerate(lines[:6])])
        content.append({"type": "text", "text": f"[PAGE {p['page']}]\n{snippet}"})
    return content


def call_llm(client: OpenAI, model: str, batch: List[Dict[str, Any]]):
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": format_window(batch)},
        ],
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {"sections": []}


def main():
    parser = argparse.ArgumentParser(description="Detect section headers within GAME span using LLM.")
    parser.add_argument("--pages", required=True, help="pages_clean.jsonl")
    parser.add_argument("--regions", required=True, help="regions.json (from portionize_regions_v1)")
    parser.add_argument("--out", required=True, help="portion_hyp.jsonl")
    parser.add_argument("--window", type=int, default=3)
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--model", default="gpt-4.1")
    parser.add_argument("--deterministic-first", dest="deterministic_first", action="store_true",
                        help="Use deterministic numeric-line detection before LLM (default).")
    parser.add_argument("--deterministic_first", dest="deterministic_first", action="store_true",
                        help=argparse.SUPPRESS)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    parser.add_argument("--skip-ai", action="store_true", help="Bypass LLM header detection and load stub portion hypotheses.")
    parser.add_argument("--stub", help="Stub portion_hyp jsonl to use when --skip-ai")
    args = parser.parse_args()

    if args.skip_ai:
        if not args.stub:
            raise SystemExit("--skip-ai set but no --stub provided for portionize_headers_v1")
        stub_rows = list(read_jsonl(args.stub))
        ensure_dir(os.path.dirname(args.out) or ".")
        save_jsonl(args.out, stub_rows)
        print(f"[skip-ai] portionize_headers_v1 copied stubs → {args.out}")
        return

    pages = list(read_jsonl(args.pages))
    pages.sort(key=lambda p: p.get("page", 0))

    reg = json.load(open(args.regions, "r", encoding="utf-8"))
    regions = reg.get("regions", []) if isinstance(reg, dict) else []
    game_spans = [r for r in regions if r.get("type") == "game" and r.get("start_page") is not None and r.get("end_page") is not None]
    if not game_spans:
        raise SystemExit("No game region found")
    # Use the full game extent (min start to max end) to avoid missing scattered spans
    start_page = min(r["start_page"] for r in game_spans)
    end_page = max(r["end_page"] for r in game_spans)

    game_pages = [p for p in pages if start_page <= p["page"] <= end_page]
    if not game_pages:
        raise SystemExit("No pages in game region")

    # deterministic pass: grab standalone numeric lines 1-400
    seen = set()
    numeric_hypos = []
    for p in game_pages:
        lines = clean_lines(p.get("clean_text") or p.get("raw_text") or "")
        for idx, line in enumerate(lines):
            m = re.match(r"^(\d{1,3})(?!\d)", line)
            if not m:
                continue
            sid_int = int(m.group(1))
            if not (1 <= sid_int <= 400):
                continue
            if sid_int in seen:
                continue
            seen.add(sid_int)
            hypo = PortionHypothesis(
                portion_id=str(sid_int),
                page_start=p["page"],
                page_end=p["page"],
                title=None,
                type="section",
                confidence=0.75,
                notes=None,
                source_window=[p["page"]],
                source_pages=[p["page"]],
                raw_text=None,
                source=["numeric_header"],
            )
            numeric_hypos.append(hypo.dict())

    # overwrite with numeric detections first
    from modules.common.utils import save_jsonl
    save_jsonl(args.out, numeric_hypos)

    # LLM refinement/extra detection
    windows = []
    i = 0
    while i < len(game_pages):
        windows.append(game_pages[i:i + args.window])
        i += args.stride

    client = OpenAI()
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    ensure_dir(os.path.dirname(args.out) or ".")

    total = len(windows)
    for idx, batch in enumerate(windows, start=1):
        res = call_llm(client, args.model, batch)
        secs = res.get("sections", []) if isinstance(res, dict) else []
        for s in secs:
            sid = s.get("section_id")
            try:
                sid_int = int(sid)
            except Exception:
                continue
            if not (1 <= sid_int <= 400):
                continue
            if sid_int in seen:
                continue
            seen.add(sid_int)
            hypo = PortionHypothesis(
                portion_id=str(sid),
                page_start=s.get("page"),
                page_end=s.get("page"),
                title=None,
                type="section",
                confidence=s.get("confidence", 0.6),
                notes=None,
                source_window=[p["page"] for p in batch],
                source_pages=[s.get("page")],
                raw_text=None,
                source=["llm_section_headers"],
            )
            append_jsonl(args.out, hypo.dict())
        logger.log("portionize", "running", current=idx, total=total,
                   message=f"headers window {idx}/{total}", artifact=args.out,
                   module_id="portionize_headers_v1")
    if not os.path.exists(args.out):
        open(args.out, "w", encoding="utf-8").close()

    logger.log("portionize", "done", current=total, total=total,
               message="headers done", artifact=args.out,
               module_id="portionize_headers_v1")
    print(f"Detected headers into {args.out}")


if __name__ == "__main__":
    main()
