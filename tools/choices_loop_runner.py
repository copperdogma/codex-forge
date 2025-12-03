import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(cmd):
    rc = subprocess.call(cmd)
    if rc != 0:
        raise SystemExit(f"Command failed: {' '.join(cmd)} rc={rc}")


def main():
    ap = argparse.ArgumentParser(description="Iterative choices loop: regex detect -> validate -> LLM escalate missing choices.")
    ap.add_argument("--portions", required=True, help="input portions (json/jsonl)")
    ap.add_argument("--out", required=True, help="output portions after loop")
    ap.add_argument("--missing", required=True, help="path to missing choices jsonl")
    ap.add_argument("--invalid", required=True, help="path to invalid targets jsonl")
    ap.add_argument("--min-target", type=int, default=1)
    ap.add_argument("--max-target", type=int, default=400)
    ap.add_argument("--model", default="gpt-4.1-mini")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--max-sections", type=int, default=50)
    ap.add_argument("--pages", help="(ignored; driver compatibility)")
    ap.add_argument("--progress-file", help="(ignored)")
    ap.add_argument("--state-file", help="(ignored)")
    ap.add_argument("--run-id", help="(ignored)")
    args = ap.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    current = args.portions

    def ensure_jsonl(path):
        if path.endswith(".jsonl"):
            return path
        data = json.load(open(path, "r", encoding="utf-8"))
        rows = list(data.values()) if isinstance(data, dict) else data
        out_path = path.replace(".json", ".jsonl")
        with open(out_path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        return out_path

    for attempt in range(1, args.retries + 1):
        print(f"[choices-loop] attempt {attempt}/{args.retries}")
        # regex detect (overwrites choices if missing; keeps existing)
        run([
            sys.executable,
            "-m", "modules.enrich.infer_choices_regex_v1.main",
            "--portions", current,
            "--out", args.out,
            "--min-target", str(args.min_target),
            "--max-target", str(args.max_target),
        ])
        current = args.out
        # validate
        run([
            sys.executable,
            "-m", "modules.enrich.choices_coverage_guard_v1.main",
            "--portions", current,
            "--out-missing", args.missing,
            "--out-invalid", args.invalid,
            "--min-target", str(args.min_target),
            "--max-target", str(args.max_target),
            "--include-text",
        ])
        missing = list(open(args.missing, "r", encoding="utf-8"))
        invalid = list(open(args.invalid, "r", encoding="utf-8"))
        print(f"[choices-loop] missing_count={len(missing)} invalid_count={len(invalid)}")
        if len(missing) == 0 and len(invalid) == 0:
            print("[choices-loop] done")
            return
        if attempt == args.retries:
            break
        # escalate missing choices
        run([
            sys.executable,
            "-m", "modules.enrich.escalate_choices_llm_v1.main",
            "--portions", current,
            "--missing", args.missing,
            "--out", args.out,
            "--model", args.model,
            "--max-sections", str(args.max_sections),
        ])
        current = args.out

    # Ensure final output is jsonl for driver stamping
    final = ensure_jsonl(current)
    if final != args.out:
        Path(args.out).unlink(missing_ok=True)
        Path(final).rename(args.out)

    print("[choices-loop] reached retry limit; missing/invalid remain")


if __name__ == "__main__":
    main()
