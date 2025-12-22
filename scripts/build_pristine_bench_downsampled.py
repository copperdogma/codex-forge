#!/usr/bin/env python3
"""Build downsampled pristine benchmark images matching old-page sizes."""
import argparse
import json
import re
from pathlib import Path
from PIL import Image

BENCH_PAGES = [
    "page-004L.png",
    "page-007R.png",
    "page-009L.png",
    "page-011.jpg",
    "page-017L.png",
    "page-017R.png",
    "page-019R.png",
    "page-020R.png",
    "page-026L.png",
    "page-035R.png",
    "page-054R.png",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Downsample pristine pages to match old benchmark sizes.")
    parser.add_argument("--old-dir", required=True, help="Directory containing old benchmark images")
    parser.add_argument("--pristine-dir", required=True, help="Directory containing pristine full images")
    parser.add_argument("--out-dir", required=True, help="Output directory for downsampled images")
    parser.add_argument("--mapping", help="JSON mapping file: [{bench_name, pristine_page}]")
    args = parser.parse_args()

    Image.MAX_IMAGE_PIXELS = None

    old_dir = Path(args.old_dir)
    pristine_dir = Path(args.pristine_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mapping = []

    mapping_data = None
    if args.mapping:
        mapping_path = Path(args.mapping)
        mapping_data = json.loads(mapping_path.read_text(encoding="utf-8"))

    if mapping_data is None:
        raise SystemExit("Missing --mapping; provide a JSON mapping for pristine pages.")

    for row in mapping_data:
        name = row["bench_name"]
        pristine_name = row["pristine_page"]
        old_path = old_dir / name
        if not old_path.exists():
            raise FileNotFoundError(f"Missing old benchmark image: {old_path}")

        pristine_path = pristine_dir / pristine_name
        if not pristine_path.exists():
            raise FileNotFoundError(f"Missing pristine page: {pristine_path}")

        with Image.open(old_path) as old_img:
            target_size = old_img.size

        with Image.open(pristine_path) as pristine_img:
            resized = pristine_img.resize(target_size, Image.LANCZOS)

        out_path = out_dir / name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        resized.save(out_path)

        mapping.append({
            "bench_name": name,
            "old_image": str(old_path),
            "pristine_image": str(pristine_path),
            "out_image": str(out_path),
            "target_page": pristine_name,
            "target_size": [target_size[0], target_size[1]],
        })

    map_path = out_dir / "mapping.json"
    map_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(mapping)} images to {out_dir}")


if __name__ == "__main__":
    main()
