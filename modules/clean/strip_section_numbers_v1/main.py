import argparse
import re
from copy import deepcopy
from typing import List

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger

SECTION_LINE_RE = re.compile(r"^\s*\d{1,3}\s*$")
RANGE_LINE_RE = re.compile(r"^\s*\d{1,3}\s*[–-]\s*\d{1,3}\s*$")
LEADING_CLUSTER_RE = re.compile(
    r"^\s*(?:\d{1,3}(?:\s*[–-]\s*\d{1,3})?[\.:\)]?)(?:\s+\d{1,3}(?:\s*[–-]\s*\d{1,3})?[\.:\)]?)*\s+"
)


def is_numberish_token(tok: str) -> bool:
    core = re.sub(r"[\W_]+", "", tok)
    if not core or len(core) > 7:
        return False
    has_digit = any(ch.isdigit() for ch in core)
    allowed = set("0123456789OIlEIeJojei")
    return has_digit and all(ch in allowed for ch in core)


def is_rangeish_token(tok: str) -> bool:
    core = tok.strip()
    return bool(re.match(r"^[0-9A-Za-z]{1,4}\s*[–-]\s*[0-9A-Za-z]{1,4}$", core))


def strip_number_lines(lines: List[str]) -> List[str]:
    """Remove lines that are just section/page numbers or simple ranges."""
    cleaned = []
    for line in lines:
        if not line.strip():
            cleaned.append("")
            continue
        tokens = line.strip().split()
        if SECTION_LINE_RE.match(line) or RANGE_LINE_RE.match(line):
            continue
        if len(tokens) == 1 and (is_numberish_token(tokens[0]) or is_rangeish_token(tokens[0])):
            continue
        cleaned.append(line.rstrip())
    return cleaned


def is_gibberish_line(line: str) -> bool:
    """Heuristic to drop obvious OCR gibberish while keeping real content."""
    text = line.strip()
    if not text:
        return False
    if set(text) <= {"—", "-", "_", "~", "*", "·", "."}:
        return True
    if len(text) < 12:
        return False
    words = [w.lower() for w in re.findall(r"[A-Za-z']+", text)]
    strong_words = {"the", "and", "you", "your", "turn", "to", "are", "with", "from", "into", "door", "fight", "gold", "skill", "stamina", "luck", "take", "lose", "gain", "open", "attack", "drink", "leave", "continue", "north", "south", "west", "east"}
    if len(words) >= 6 and not (strong_words & set(words)):
        return True
    # discard lines that are mostly non-letters (symbols/garbled)
    alpha = sum(ch.isalpha() for ch in text)
    ratio = alpha / max(len(text), 1)
    if ratio < 0.35:
        # allow common words to escape the filter
        keep_words = ("turn", "skill", "stamina", "luck", "gold", "potion", "fight", "door", "attack")
        lower = text.lower()
        if not any(w in lower for w in keep_words):
            return True
    # drop pure dash/box-drawing separators
    if set(text) <= {"—", "-", "_", "~", "*", "·", "."}:
        return True
    return False


def drop_leading_section_prefix(lines: List[str], section_id: str | None) -> List[str]:
    """Strip leading numeric clusters (section/page numbers) from the first non-empty line only."""

    def token_matches_section(tok: str, section: str | None) -> bool:
        if not section or not section.isdigit():
            return False
        clean = re.sub(r"\D", "", tok)
        return clean == section

    for idx, line in enumerate(lines):
        if not line.strip():
            continue

        new_line = LEADING_CLUSTER_RE.sub("", line, count=1).lstrip()
        tokens = new_line.split()
        removed = 0

        while tokens:
            tok = tokens[0]
            next_is_number = len(tokens) > 1 and is_numberish_token(tokens[1])
            drop = False
            if token_matches_section(tok, section_id):
                drop = True
            elif is_rangeish_token(tok):
                drop = True
            elif is_numberish_token(tok) and (next_is_number or removed > 0):
                drop = True
            elif tok[:1].isdigit() and any(ch.isalpha() for ch in tok) and len(tok) <= 4:
                drop = True

            if drop:
                tokens.pop(0)
                removed += 1
                continue
            break

        new_line = " ".join(tokens).lstrip()
        lines[idx] = new_line
        break
    return lines


def collapse_blank_lines(lines: List[str]) -> List[str]:
    """Collapse multiple blank lines to a single blank line, trim edges."""
    out = []
    for line in lines:
        if not line.strip():
            if out and out[-1] == "":
                continue
            out.append("")
        else:
            out.append(line)
    # trim leading/trailing blanks
    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()
    return out


def normalize_newlines(text: str, section_id: str | None = None) -> str:
    if not text:
        return text
    lines = text.splitlines()
    lines = strip_number_lines(lines)
    lines = drop_leading_section_prefix(lines, section_id)
    lines = [ln for ln in lines if not is_gibberish_line(ln)]
    lines = collapse_blank_lines(lines)
    return "\n\n".join(lines)


def process_portion(portion: dict, module_id: str) -> dict:
    updated = deepcopy(portion)
    raw_text = portion.get("raw_text") or ""
    cleaned = normalize_newlines(raw_text, portion.get("section_id"))
    updated["raw_text"] = cleaned

    # drop empty created_at to reduce clutter
    if updated.get("created_at") is None:
        updated.pop("created_at", None)

    # preserve existing metadata and mark source
    existing_source = updated.get("source") or []
    if isinstance(existing_source, list):
        updated["source"] = list({*existing_source, module_id})
    else:
        updated["source"] = [str(existing_source), module_id]

    updated["module_id"] = module_id
    return updated


def main():
    parser = argparse.ArgumentParser(description="Strip section/page numbers from section text and normalize paragraphs.")
    parser.add_argument("--portions", required=True, help="Input portions_enriched.jsonl")
    parser.add_argument("--out", required=True, help="Output cleaned portions JSONL")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    module_id = "strip_section_numbers_v1"
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    portions = list(read_jsonl(args.portions))
    total = len(portions)
    if total == 0:
        raise SystemExit("No portions found in input file")

    logger.log("clean", "running", current=0, total=total,
               message=f"Cleaning {total} portions", artifact=args.out, module_id=module_id)

    out_rows = []
    for idx, portion in enumerate(portions, start=1):
        cleaned = process_portion(portion, module_id)
        out_rows.append(cleaned)
        logger.log("clean", "running", current=idx, total=total,
                   message=f"Cleaned section {portion.get('section_id')}", artifact=args.out, module_id=module_id)

    save_jsonl(args.out, out_rows)
    logger.log("clean", "done", current=total, total=total,
               message=f"Cleaned {total} portions", artifact=args.out, module_id=module_id,
               schema_version="enriched_portion_v1")
    print(f"Wrote cleaned portions → {args.out}")


if __name__ == "__main__":
    main()
