import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from modules.common.text_quality import spell_garble_metrics
from modules.common.utils import ensure_dir, save_json, append_jsonl


def _read_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                yield obj


def _extract_lines(obj: Dict[str, Any]) -> List[str]:
    lines = obj.get("lines") or []
    out: List[str] = []
    for ln in lines:
        if isinstance(ln, dict):
            t = ln.get("text")
            if isinstance(t, str):
                out.append(t)
        elif isinstance(ln, str):
            out.append(ln)
    return out


def _page_key_from_obj(obj: Dict[str, Any]) -> Optional[str]:
    img = obj.get("image")
    if isinstance(img, str) and "page-" in img and img.endswith(".png"):
        return Path(img).stem.replace("page-", "")
    # Fall back to numeric page if present
    p = obj.get("page")
    if isinstance(p, int):
        return str(p)
    return None


def summarize_rows(rows: List[Dict[str, Any]], *, top_n: int) -> Dict[str, Any]:
    mixed = Counter()
    suspicious = Counter()
    oov = Counter()

    for r in rows:
        for w, n in (r.get("dictionary_oov_examples") or []):
            if isinstance(w, str) and isinstance(n, int):
                oov[w] += n
        for w, n in (r.get("char_confusion_examples") or []):
            if isinstance(w, str) and isinstance(n, int):
                mixed[w] += n
        for w, n in (r.get("char_confusion_suspicious_examples") or []):
            if isinstance(w, str) and isinstance(n, int):
                suspicious[w] += n

    return {
        "total_rows": len(rows),
        "rows_with_dictionary_oov": sum(1 for r in rows if (r.get("dictionary_oov_ratio") or 0) > 0),
        "rows_with_suspicious_mixed": sum(1 for r in rows if (r.get("char_confusion_suspicious_examples") or [])),
        "top_dictionary_oov": oov.most_common(top_n),
        "top_mixed_alnum": mixed.most_common(top_n),
        "top_suspicious_mixed": suspicious.most_common(top_n),
    }


def infer_input_from_inputs(inputs: List[str]) -> Optional[str]:
    if not inputs:
        return None
    first = Path(inputs[0]).resolve()
    if first.is_file():
        # If the user points to a jsonl, just use it.
        if first.suffix.lower() in {".jsonl", ".json"}:
            return str(first)
        base = first.parent
    else:
        base = first
    # Try common canonical outputs
    candidates = [
        base / "pagelines_final.jsonl",
        base / "pagelines_reconstructed.jsonl",
        base / "elements_core_typed.jsonl",
        base / "elements_core.jsonl",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return str(c)
    return None


def main():
    ap = argparse.ArgumentParser(description="Generate a lightweight text-quality report from a JSONL artifact.")
    ap.add_argument("--in", dest="in_path", help="Input JSONL file (pagelines/elements).")
    ap.add_argument("--inputs", nargs="*", help="Optional driver inputs; used to infer an input file.")
    ap.add_argument("--out", required=True, help="Output JSONL rows.")
    ap.add_argument("--report", required=True, help="Output JSON summary report.")
    ap.add_argument("--top-n", dest="top_n", type=int, default=20, help="Top-N examples to include in report.")
    args = ap.parse_args()

    in_path = args.in_path or infer_input_from_inputs(args.inputs or [])
    if not in_path:
        raise SystemExit("Missing input; pass --in or --inputs pointing at a run dir/artifact.")
    if not os.path.exists(in_path):
        raise SystemExit(f"Input not found: {in_path}")

    ensure_dir(os.path.dirname(args.out) or ".")
    ensure_dir(os.path.dirname(args.report) or ".")

    rows: List[Dict[str, Any]] = []
    for obj in _read_jsonl(in_path):
        page_key = _page_key_from_obj(obj)
        lines = _extract_lines(obj)
        metrics = spell_garble_metrics(lines)
        row = {
            "page": page_key,
            "dictionary_score": metrics["dictionary_score"],
            "dictionary_oov_ratio": metrics["dictionary_oov_ratio"],
            "dictionary_total_words": metrics["dictionary_total_words"],
            "dictionary_oov_words": metrics["dictionary_oov_words"],
            "dictionary_oov_examples": metrics["dictionary_oov_examples"],
            "dictionary_suspicious_oov_words": metrics["dictionary_suspicious_oov_words"],
            "dictionary_suspicious_oov_examples": metrics["dictionary_suspicious_oov_examples"],
            "char_confusion_score": metrics["char_confusion_score"],
            "char_confusion_mixed_ratio": metrics["char_confusion_mixed_ratio"],
            "char_confusion_examples": metrics["char_confusion_examples"],
            "char_confusion_suspicious_examples": metrics.get("char_confusion_suspicious_examples", []),
            "char_count": sum(len(l) for l in lines),
            "line_count": len([l for l in lines if l.strip()]),
            "source_file": os.path.abspath(in_path),
        }
        rows.append(row)
        append_jsonl(args.out, row)

    report = {
        "schema_version": "text_quality_report_v1",
        "input": os.path.abspath(in_path),
        "out_rows": os.path.abspath(args.out),
        "summary": summarize_rows(rows, top_n=args.top_n),
    }
    save_json(args.report, report)
    print(f"Wrote rows: {args.out}\nWrote report: {args.report}")


if __name__ == "__main__":
    main()

