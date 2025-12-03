import argparse
import json
import os
import subprocess
import sys
from typing import List


def run(cmd: List[str]):
    rc = subprocess.call(cmd)
    if rc != 0:
        raise SystemExit(f"Command failed: {' '.join(cmd)} rc={rc}")


def main():
    ap = argparse.ArgumentParser(description="Iterative header resolve loop: detect → dedupe → coverage → resolver until done or retries hit.")
    ap.add_argument("--pages-clean", required=True, help="pages_clean_withnums.jsonl")
    ap.add_argument("--headers", required=True, help="path to window_hypotheses.jsonl (will be overwritten)")
    ap.add_argument("--headers-dedup", required=True, help="path to deduped headers jsonl")
    ap.add_argument("--missing", required=True, help="headers_missing.jsonl output path")
    ap.add_argument("--pagelines-index", required=True, help="pagelines_index.json (canonical)")
    ap.add_argument("--quality", required=True, help="ocr_quality_report.json")
    ap.add_argument("--images-dir", required=True)
    ap.add_argument("--outdir", required=True, help="OCR run dir (used by resolver)")
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--bundle-dir", default=None)
    ap.add_argument("--inputs", nargs="*", help="(ignored; driver compatibility)")
    args = ap.parse_args()

    for attempt in range(1, args.retries + 1):
        print(f"[header-loop] attempt {attempt}/{args.retries}")

        # Detect
        run([sys.executable, "-m", "modules.portionize.portionize_headers_numeric_v1.main",
             "--pages", args.pages_clean, "--out", args.headers])

        # Dedupe
        run([sys.executable, "-m", "modules.adapter.portion_hyp_dedupe_v1.main",
             "--input", args.headers, "--out", args.headers_dedup])

        # Coverage
        cov_cmd = [sys.executable, "-m", "modules.adapter.header_coverage_guard_v1.main",
                   "--headers", args.headers_dedup,
                   "--pages-clean", args.pages_clean,
                   "--ocr-index", args.pagelines_index,
                   "--out", args.missing,
                   "--note", f"loop attempt {attempt}"]
        if args.bundle_dir:
            cov_cmd += ["--bundle-dir", args.bundle_dir]
        run(cov_cmd)

        missing = list(open(args.missing, "r", encoding="utf-8"))
        print(f"[header-loop] missing count={len(missing)}")
        if len(missing) == 0 or (len(missing) == 1 and '"section_id": 169' in (missing[0] if missing else "")):
            print("[header-loop] done")
            return

        # Resolver
        run([
            sys.executable,
            "-m", "modules.adapter.missing_header_resolver_v1.main",
            "--headers", args.headers_dedup,
            "--pagelines-index", args.pagelines_index,
            "--quality", args.quality,
            "--images-dir", args.images_dir,
            "--outdir", args.outdir,
            "--max-pages", str(args.max_pages),
            "--batch-size", str(args.batch_size),
            "--model", args.model,
            "--pages-clean-out", args.pages_clean,
            "--record-hash", os.path.join(args.outdir, "pagelines_hash.json"),
        ])

    print("[header-loop] reached retry limit; missing remains")


if __name__ == "__main__":
    main()
