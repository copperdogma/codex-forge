import argparse
import glob
import os
import sys
import pathlib
from typing import List

repo_root = pathlib.Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from utils import ensure_dir, save_jsonl


def read_files(paths: List[str]) -> List[dict]:
    pages = []
    for idx, path in enumerate(sorted(paths), start=1):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        pages.append({
            "page": idx,
            "source_path": os.path.abspath(path),
            "image": None,
            "text": text
        })
    return pages


def main():
    parser = argparse.ArgumentParser(description="Ingest text/Markdown/HTML files into pages_raw.jsonl")
    parser.add_argument("--input_glob", "--input-glob", dest="input_glob", required=True,
                        help="Glob for input text files (e.g., 'input/text/**/*.md')")
    parser.add_argument("--outdir", required=True, help="Output dir for pages_raw.jsonl")
    parser.add_argument("--start_page", "--start-page", dest="start_page", type=int, default=1,
                        help="Starting page number")
    args = parser.parse_args()

    paths = glob.glob(args.input_glob, recursive=True)
    if not paths:
        raise SystemExit(f"No files matched glob: {args.input_glob}")

    ensure_dir(args.outdir)
    pages = []
    for offset, path in enumerate(sorted(paths), start=0):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        pages.append({
            "page": args.start_page + offset,
            "source_path": os.path.abspath(path),
            "image": None,
            "text": text
        })

    save_jsonl(os.path.join(args.outdir, "pages_raw.jsonl"), pages)
    print(f"Wrote {len(pages)} pages to {os.path.join(args.outdir, 'pages_raw.jsonl')}")


if __name__ == "__main__":
    main()
