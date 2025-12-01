import argparse
import os
import re
from modules.common.utils import read_jsonl, ensure_dir, save_jsonl, ProgressLogger
from schemas import PortionHypothesis

PAGE_RE = re.compile(r"^\s*\d{1,3}[–-]\d{1,3}\s*")


def clean_lines(text: str):
    lines = []
    for line in (text or "").splitlines():
        line = PAGE_RE.sub("", line).strip()
        if line:
            lines.append(line)
    return lines


def main():
    parser = argparse.ArgumentParser(description="Pure numeric header detector (1-400) over cleaned pages.")
    parser.add_argument("--pages", required=True, help="pages_clean.jsonl")
    parser.add_argument("--out", required=True, help="portion_hyp.jsonl")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    parser.add_argument("--fuzzy", action="store_true", default=True, help="Enable fuzzy detection (digits followed by up to 2 non-digits)")
    args = parser.parse_args()

    pages = list(read_jsonl(args.pages))
    pages.sort(key=lambda p: p.get("page", 0))

    seen = set()
    hypos = []
    for p in pages:
        for line in clean_lines(p.get("clean_text") or p.get("raw_text") or ""):
            # Tier 1: strict / fused
            m = re.match(r"^(\d{1,3})(?!\d)", line)
            sid = int(m.group(1)) if m else None

            # Tier 2: fuzzy (digits followed by up to 2 non-digits) if requested
            if sid is None and args.fuzzy:
                m2 = re.match(r"^(\d{1,3})\D{0,2}", line)
                sid = int(m2.group(1)) if m2 else None

            if sid is None:
                continue
            if not (1 <= sid <= 400):
                continue
            if sid in seen:
                continue
            seen.add(sid)
            hypo = PortionHypothesis(
                portion_id=str(sid),
                page_start=p["page"],
                page_end=p["page"],
                title=None,
                type="section",
                confidence=0.70 if sid and m is None else 0.75,
                notes=None,
                source_window=[p["page"]],
                source_pages=[p["page"]],
                raw_text=None,
                source=["numeric_header_fuzzy" if m is None else "numeric_header"],
            )
            hypos.append(hypo.dict())

    ensure_dir(os.path.dirname(args.out) or ".")
    save_jsonl(args.out, hypos)
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("portionize", "done", current=len(hypos), total=len(hypos),
               message=f"numeric headers {len(hypos)}", artifact=args.out,
               module_id="portionize_headers_numeric_v1", schema_version="portion_hyp_v1")
    print(f"Numeric headers detected {len(hypos)} → {args.out}")


if __name__ == "__main__":
    main()
