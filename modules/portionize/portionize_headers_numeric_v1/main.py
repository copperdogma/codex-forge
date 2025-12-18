import argparse
import os
import re
import json
from modules.common.utils import read_jsonl, ensure_dir, save_jsonl, ProgressLogger
from modules.common.macro_section import macro_section_for_page
from schemas import PortionHypothesis

PAGE_RE = re.compile(r"^\s*\d{1,3}[–-]\d{1,3}\s*")
NUM_TOKEN_RE = re.compile(r"(\d{1,3})")


def clean_lines(text: str):
    lines = []
    for line in (text or "").splitlines():
        line = PAGE_RE.sub("", line).strip()
        if line:
            lines.append(line)
    return lines


def main():
    parser = argparse.ArgumentParser(description="Numeric header detector (1-400) over cleaned pages; tolerant of inline/fused numbers.")
    parser.add_argument("--pages", required=True, help="pages_clean.jsonl")
    parser.add_argument("--out", required=True, help="portion_hyp.jsonl")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    parser.add_argument("--fuzzy", action="store_true", default=True, help="Enable fuzzy detection (digits followed by a few non-digits)")
    parser.add_argument("--max-per-page", type=int, default=12, help="Cap hypotheses per page to limit noise.")
    parser.add_argument("--coarse-segments", "--coarse_segments", dest="coarse_segments",
                        help="Optional coarse_segments.json or merged_segments.json for macro_section tagging")
    args = parser.parse_args()

    pages = list(read_jsonl(args.pages))
    pages.sort(key=lambda p: p.get("page", 0))

    coarse_segments = None
    if args.coarse_segments:
        try:
            with open(args.coarse_segments, "r", encoding="utf-8") as f:
                coarse_segments = json.load(f)
        except Exception:
            coarse_segments = None

    hypos = []
    for p in pages:
        raw_lines = clean_lines(p.get("clean_text") or p.get("raw_text") or "")
        candidates = []
        for i, line in enumerate(raw_lines):
            trimmed = line.strip()
            tokens = []
            for m in NUM_TOKEN_RE.finditer(trimmed):
                try:
                    sid = int(m.group(1))
                except Exception:
                    continue
                if not (1 <= sid <= 400):
                    continue
                tokens.append((sid, m.start(), m.end()))
            if not tokens:
                continue

            for sid, s, e in tokens:
                at_start = s == len(trimmed) - len(trimmed.lstrip())
                standalone = len(trimmed) <= 4 or re.fullmatch(r"\d{1,3}", trimmed)
                confidence = 0.8 if standalone else (0.75 if at_start else 0.65)
                if not standalone and at_start and args.fuzzy and re.match(r"^\d{1,3}\D{0,2}", trimmed):
                    confidence = max(confidence, 0.7)

                # We rely on later guards to filter page numbers; keep detection permissive here.

                candidates.append({
                    "sid": sid,
                    "conf": confidence,
                    "page": p["page"],
                    "source": "numeric_header_inline" if not (standalone or at_start) else ("numeric_header_fuzzy" if confidence < 0.75 else "numeric_header"),
                    "notes": None if (standalone or at_start) else "inline_number",
                })

        candidates.sort(key=lambda c: (-c["conf"], c["sid"]))
        for c in candidates[: args.max_per_page]:
            hypos.append(PortionHypothesis(
                portion_id=str(c["sid"]),
                page_start=c["page"],
                page_end=c["page"],
                title=None,
                type="section",
                confidence=c["conf"],
                notes=c["notes"],
                source_window=[c["page"]],
                source_pages=[c["page"]],
                raw_text=None,
                macro_section=macro_section_for_page(c["page"], coarse_segments),
                source=[c["source"]],
            ).dict())

    ensure_dir(os.path.dirname(args.out) or ".")
    save_jsonl(args.out, hypos)
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("portionize", "done", current=len(hypos), total=len(hypos),
               message=f"numeric headers {len(hypos)}", artifact=args.out,
               module_id="portionize_headers_numeric_v1", schema_version="portion_hyp_v1")
    print(f"Numeric headers detected {len(hypos)} → {args.out}")


if __name__ == "__main__":
    main()
