import argparse
import hashlib
import json
from modules.common.utils import save_json


def file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="Record or verify hash of pagelines_index.json to prevent stale OCR use.")
    ap.add_argument("--index", required=True, help="pagelines_index.json to hash")
    ap.add_argument("--expect", help="Expected hash; if set, will fail on mismatch")
    ap.add_argument("--out", help="Where to write the computed hash (json)")
    args = ap.parse_args()

    h = file_hash(args.index)
    if args.expect and args.expect != h:
        raise SystemExit(f"Hash mismatch: expected {args.expect}, got {h}")
    if args.out:
        save_json(args.out, {"pagelines_index_hash": h})
    print(h)


if __name__ == "__main__":
    main()
