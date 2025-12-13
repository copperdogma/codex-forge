#!/usr/bin/env python3
"""
Generic regression check for suspicious OCR-like token patterns in JSONL artifacts.

This is intentionally pattern-based (not book-specific):
- Mixed alphanumeric tokens (e.g., y0u, f0110win9)
- Vowel-less long fragments (e.g., sxrll)

Use for smoke/regression checks to detect reintroduced garble without hard-coding
specific replacements or page IDs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_ORDINAL_RE = re.compile(r"^\d+(st|nd|rd|th)$", re.IGNORECASE)
_PAGES_N_RE = re.compile(r"^pages?\d+$", re.IGNORECASE)


def _iter_texts_from_obj(obj: Dict[str, Any]) -> Iterable[str]:
    # Common shapes:
    # - pagelines: {"lines":[{"text":...}, ...]}
    # - elements: {"text": "..."}
    if isinstance(obj.get("text"), str):
        yield obj["text"]

    lines = obj.get("lines")
    if isinstance(lines, list):
        for ln in lines:
            if isinstance(ln, dict) and isinstance(ln.get("text"), str):
                yield ln["text"]
            elif isinstance(ln, str):
                yield ln


def _tokenize(text: str) -> List[str]:
    return [m.group(0) for m in _WORD_RE.finditer(text or "")]


def suspicious_tokens(tokens: List[str], *, min_len: int) -> Tuple[List[str], List[str]]:
    mixed: List[str] = []
    vowel_less: List[str] = []
    vowels = set("aeiouyAEIOUY")
    for tok in tokens:
        if len(tok) < min_len:
            continue
        # Ignore common, generally-legit mixed tokens.
        # These are not OCR garble patterns; they occur in normal prose/front matter.
        if _ORDINAL_RE.match(tok) or _PAGES_N_RE.match(tok):
            continue
        has_alpha = any(ch.isalpha() for ch in tok)
        has_digit = any(ch.isdigit() for ch in tok)
        if has_alpha and has_digit:
            mixed.append(tok)
            continue
        if tok.isalpha() and not any(ch in vowels for ch in tok):
            vowel_less.append(tok)
    return mixed, vowel_less


def main() -> int:
    ap = argparse.ArgumentParser(description="Fail if suspicious OCR-like tokens are found in JSONL artifacts.")
    ap.add_argument("--file", required=True, help="Input JSONL file to scan.")
    ap.add_argument("--max-mixed", type=int, default=0, help="Max allowed mixed alnum tokens (default 0).")
    ap.add_argument("--max-vowel-less", type=int, default=0, help="Max allowed vowel-less alpha tokens (default 0).")
    ap.add_argument("--min-len", type=int, default=4, help="Minimum token length to consider suspicious (default 4).")
    ap.add_argument("--top", type=int, default=20, help="How many examples to print (default 20).")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists() or not path.is_file():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2

    mixed_counter: Counter[str] = Counter()
    vowel_less_counter: Counter[str] = Counter()
    scanned_rows = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            scanned_rows += 1
            for txt in _iter_texts_from_obj(obj):
                toks = _tokenize(txt)
                mixed, vowel_less = suspicious_tokens(toks, min_len=args.min_len)
                mixed_counter.update(mixed)
                vowel_less_counter.update(vowel_less)

    mixed_total = sum(mixed_counter.values())
    vowel_less_total = sum(vowel_less_counter.values())

    ok = (mixed_total <= args.max_mixed) and (vowel_less_total <= args.max_vowel_less)

    if ok:
        print(f"OK: scanned_rows={scanned_rows} mixed={mixed_total} vowel_less={vowel_less_total}")
        return 0

    print(f"FAIL: scanned_rows={scanned_rows} mixed={mixed_total} (max {args.max_mixed}) "
          f"vowel_less={vowel_less_total} (max {args.max_vowel_less})")
    if mixed_total:
        print("Top mixed tokens:")
        for tok, n in mixed_counter.most_common(args.top):
            print(f"  {tok}\t{n}")
    if vowel_less_total:
        print("Top vowel-less tokens:")
        for tok, n in vowel_less_counter.most_common(args.top):
            print(f"  {tok}\t{n}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
