import argparse
import json
import re
from typing import Any, Dict, List

from modules.common.utils import ProgressLogger, read_jsonl, save_jsonl

SECTION_RE = re.compile(r"^\s*(\d{1,3})(?:\D|$)")


def load_portions(path: str) -> List[Dict[str, Any]]:
    return list(read_jsonl(path))


def check_section_number(portion: Dict[str, Any]) -> Dict[str, Any]:
    section_id = portion.get("section_id") or portion.get("portion_id")
    text = (portion.get("raw_text") or portion.get("text") or "").strip()
    snippet = text.splitlines()[0] if text else ""
    match = SECTION_RE.match(snippet)
    if section_id and isinstance(section_id, (int, str)) and str(section_id).isdigit():
        if not match or match.group(1) != str(section_id):
            return {
                "portion_id": portion.get("portion_id"),
                "section_id": section_id,
                "reason": "missing_or_misaligned_section_number",
                "snippet": snippet[:80],
                "page_start": portion.get("page_start"),
            }
    return {}


def main():
    parser = argparse.ArgumentParser(description="Detect missing or misaligned section numbers.")
    parser.add_argument("--portions", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    rows = load_portions(args.portions)
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("section_number", "running", current=0, total=len(rows),
               artifact=args.out, module_id="section_number_validator_v1", message="Checking section numbers")
    warnings = []
    for idx, portion in enumerate(rows, start=1):
        result = check_section_number(portion)
        if result:
            warnings.append(result)
        if idx % 50 == 0:
            logger.log("section_number", "running", current=idx, total=len(rows),
                       artifact=args.out, module_id="section_number_validator_v1",
                       message=f"Checked {idx}/{len(rows)} portions")
    save_jsonl(args.out, warnings)
    logger.log("section_number", "done", current=len(rows), total=len(rows),
               artifact=args.out, module_id="section_number_validator_v1", message=f"Found {len(warnings)} mismatched sections")

if __name__ == "__main__":
    main()
