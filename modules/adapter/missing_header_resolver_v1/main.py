"""Resolve missing section headers with targeted GPT-4V re-OCR.

Steps:
1) Read detected headers; compute missing IDs (1-400).
2) Map each missing ID to candidate pages: nearest prev/next detected IDs' pages ±1.
3) Run escalate_gpt4v_iter_v1 on the candidate page set (bounded by --max-pages).
4) Emit updated pagelines_index/quality into an outdir and a JSON evidence report.

Generic, no book-specific tweaks.
"""

import argparse
import json
import os
import subprocess
import sys
import hashlib
from typing import Dict, List, Set

from modules.common.utils import read_jsonl, save_json, ProgressLogger


def load_headers(path: str) -> Dict[int, int]:
    by_id = {}
    for row in read_jsonl(path):
        try:
            sid = int(row.get("portion_id"))
            page = int(row.get("page_start"))
            by_id[sid] = page
        except Exception:
            continue
    return by_id


def infer_candidate_pages(missing: List[int], by_id: Dict[int, int]) -> Set[int]:
    pages: Set[int] = set()
    ids = sorted(by_id.keys())
    for mid in missing:
        lower = [i for i in ids if i < mid]
        upper = [i for i in ids if i > mid]
        close_pages = []
        if lower:
            close_pages.append(by_id[max(lower)])
        if upper:
            close_pages.append(by_id[min(upper)])
        for p in close_pages:
            pages.update([p - 1, p, p + 1])
    return {p for p in pages if p > 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headers", help="portion_hyp jsonl (will be overwritten if escalation runs)")
    ap.add_argument("--inputs", nargs="*", help="alternative inputs list (use first)")
    ap.add_argument("--pagelines-index", required=True, help="source pagelines_index.json")
    ap.add_argument("--quality", required=True, help="source ocr_quality_report.json")
    ap.add_argument("--images-dir", required=True)
    ap.add_argument("--outdir", required=True, help="outdir for escalated pagelines (env vars expanded)")
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--pages-clean-out", help="Path to write cleaned pages for escalated index (temporary)")
    ap.add_argument("--dry-run", action="store_true", help="Skip GPT-4V calls; just emit report")
    ap.add_argument("--index-hash", help="Expected hash of pagelines_index.json; fail if mismatch (prevents stale inputs).")
    ap.add_argument("--record-hash", help="Where to write the hash used (for downstream checks).")
    args = ap.parse_args()

    def expand_env(val: str):
        if not isinstance(val, str):
            return val
        if val.startswith("${") and val.endswith("}"):
            key = val[2:-1]
            return os.environ.get(key, val)
        return os.path.expandvars(val)

    hdr_path = args.headers or (args.inputs[0] if args.inputs else None)
    if not hdr_path:
        raise SystemExit("Must provide --headers or --inputs")

    def file_hash(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    logger = ProgressLogger()

    by_id = load_headers(hdr_path)
    current_hash = file_hash(args.pagelines_index)
    if args.index_hash and args.index_hash != current_hash:
        raise SystemExit(f"pagelines_index hash mismatch (got {current_hash}, expected {args.index_hash}); refusing to run to avoid stale OCR")
    if args.record_hash:
        save_json(args.record_hash, {"pagelines_index_hash": current_hash})
    all_ids = set(range(1, 401))
    missing = sorted(list(all_ids - set(by_id.keys())))

    absent = []
    # Known-missing marker (book-specific, but harmless)
    for mid in (169, 170):
        if mid in missing:
            missing.remove(mid)
            absent.append(mid)

    candidates = list(sorted(infer_candidate_pages(missing, by_id)))
    if len(candidates) > args.max_pages:
        candidates = candidates[: args.max_pages]

    report = {
        "missing_before": missing + absent,
        "absent_marked": absent,
        "candidate_pages": candidates,
        "outdir": args.outdir,
        "headers_path": hdr_path,
    }

    logger.log("adapter", "running", current=0, total=len(candidates), message=f"missing={len(missing)+len(absent)} candidates={len(candidates)}")

    if candidates and not args.dry_run:
        pages_arg = ",".join(str(p) for p in candidates)
        cmd = [
            sys.executable,
            "-m",
            "modules.adapter.escalate_gpt4v_iter_v1.main",
            "--index",
            args.pagelines_index,
            "--quality",
            args.quality,
            "--images-dir",
            args.images_dir,
            "--outdir",
            args.outdir,
            "--model",
            args.model,
            "--pages",
            pages_arg,
            "--max-pages",
            str(args.max_pages),
            "--batch-size",
            str(args.batch_size),
        ]
        logger.log("adapter", "running", current=0, total=len(candidates), message=f"escalating {len(candidates)} pages", artifact=args.outdir)
        rc = subprocess.call(cmd)
        if rc != 0:
            raise SystemExit(f"escalate_gpt4v_iter_v1 failed with code {rc}")

        # Re-clean escalated pagelines and rerun numeric headers to overwrite the headers file
        escalated_index = os.path.join(args.outdir, "pagelines_index.json")
        if os.path.exists(escalated_index):
            pages_clean = args.pages_clean_out or os.path.join(args.outdir, "pages_clean.jsonl")
            # pagelines_to_clean
            logger.log("adapter", "running", current=0, total=1, message="re-clean escalated pagelines", artifact=pages_clean)
            rc = subprocess.call(
                [
                    sys.executable,
                    "-m",
                    "modules.intake.pagelines_to_clean_v1.main",
                    "--index",
                    escalated_index,
                    "--out",
                    pages_clean,
                ]
            )
            if rc != 0:
                raise SystemExit(f"pagelines_to_clean_v1 failed with code {rc}")

            # rerun numeric headers (fuzzy on by default) writing back to headers path
            logger.log("adapter", "running", current=0, total=1, message="rerun numeric headers", artifact=hdr_path)
            rc = subprocess.call(
                [
                    sys.executable,
                    "-m",
                    "modules.portionize.portionize_headers_numeric_v1.main",
                    "--pages",
                    pages_clean,
                    "--out",
                    hdr_path,
                ]
            )
            if rc != 0:
                raise SystemExit(f"portionize_headers_numeric_v1 failed with code {rc}")

            # record added/seen count
            try:
                new_by_id = load_headers(hdr_path)
                report["headers_after"] = len(new_by_id)
            except Exception:
                pass

    if not candidates:
        logger.log("adapter", "done", current=0, total=0, message="no candidates; skipping escalation")
    save_json(os.path.join(args.outdir, "missing_header_report.json"), report)
    logger.log("adapter", "done", current=len(candidates), total=len(candidates), message="resolver complete", artifact=args.outdir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
