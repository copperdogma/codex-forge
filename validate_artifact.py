import argparse
from typing import Dict, Type
from pydantic import BaseModel, ValidationError

from modules.common.utils import read_jsonl
from schemas import PortionHypothesis, LockedPortion, ResolvedPortion, EnrichedPortion, PageDoc, CleanPage


SCHEMA_MAP: Dict[str, Type[BaseModel]] = {
    "page_doc_v1": PageDoc,
    "clean_page_v1": CleanPage,
    "portion_hyp_v1": PortionHypothesis,
    "locked_portion_v1": LockedPortion,
    "resolved_portion_v1": ResolvedPortion,
    "enriched_portion_v1": EnrichedPortion,
}


def main():
    parser = argparse.ArgumentParser(description="Validate artifact JSONL against schema.")
    parser.add_argument("--schema", required=True, choices=SCHEMA_MAP.keys())
    parser.add_argument("--file", required=True, help="Path to JSONL artifact")
    args = parser.parse_args()

    model_cls = SCHEMA_MAP[args.schema]
    total = 0
    errors = 0
    for row in read_jsonl(args.file):
        total += 1
        try:
            model_cls(**row)
        except ValidationError as e:
            errors += 1
            print(f"[ERROR] row {total}: {e}")

    if errors:
        print(f"Validation finished with {errors} errors out of {total} rows.")
        raise SystemExit(1)
    else:
        print(f"Validation OK: {total} rows match {args.schema}")


if __name__ == "__main__":
    main()
