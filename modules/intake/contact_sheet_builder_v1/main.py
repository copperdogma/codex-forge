import argparse
import json
import math
import os
from pathlib import Path
from typing import Dict, List, Any

from PIL import Image, ImageDraw, ImageFont
import subprocess


def render_pdf_to_images(pdf: Path, out_dir: Path, dpi: int, image_format: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt_flag = "-jpeg" if image_format.lower() == "jpeg" else "-png"
    base = out_dir / "page"
    cmd = ["pdftoppm", fmt_flag, "-r", str(dpi), str(pdf), str(base)]
    subprocess.run(cmd, check=True)
    return out_dir

from modules.common.utils import ensure_dir


def load_font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def make_contact_sheets(
    input_dir: Path,
    output_dir: Path,
    max_width: int = 200,
    grid_cols: int = 5,
    grid_rows: int = 4,
    pad: int = 10,
    number_overlay: bool = True,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    images = sorted([p for p in input_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}])
    tiles_per_sheet = grid_cols * grid_rows
    manifest: List[Dict[str, Any]] = []
    font = load_font(18)

    for sheet_idx in range(math.ceil(len(images) / tiles_per_sheet)):
        sheet_images = images[sheet_idx * tiles_per_sheet : (sheet_idx + 1) * tiles_per_sheet]
        thumbs = []
        max_h = 0
        for idx, path in enumerate(sheet_images):
            im = Image.open(path)
            w, h = im.size
            scale = max_width / float(w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            thumb = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
            if number_overlay:
                draw = ImageDraw.Draw(thumb)
                label = str(sheet_idx * tiles_per_sheet + idx + 1)
                draw.rectangle([0, 0, 40, 24], fill=0)
                draw.text((4, 3), label, font=font, fill=255)
            thumbs.append((path, thumb, im.size))
            max_h = max(max_h, new_h)

        sheet_w = grid_cols * max_width + (grid_cols + 1) * pad
        sheet_h = grid_rows * max_h + (grid_rows + 1) * pad
        sheet = Image.new("RGB", (sheet_w, sheet_h), color=(245, 245, 245))

        for local_idx, (path, thumb, orig_size) in enumerate(thumbs):
            row = local_idx // grid_cols
            col = local_idx % grid_cols
            x = pad + col * (max_width + pad)
            y = pad + row * (max_h + pad)
            sheet.paste(thumb, (x, y))
            manifest.append(
                {
                    "schema_version": "contact_sheet_manifest_v1",
                    "sheet_id": f"sheet-{sheet_idx:03d}",
                    "tile_index": local_idx,
                    "source_image": path.name,
                    "display_number": sheet_idx * tiles_per_sheet + local_idx + 1,
                    "sheet_path": str(output_dir / f"sheet-{sheet_idx:03d}.jpg"),
                    "tile_bbox": {"x": x, "y": y, "width": thumb.width, "height": thumb.height},
                    "orig_size": {"width": orig_size[0], "height": orig_size[1]},
                }
            )

        sheet_path = output_dir / f"sheet-{sheet_idx:03d}.jpg"
        sheet.save(sheet_path, quality=85)

    manifest_path = output_dir / "contact_sheet_manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as f:
        for row in manifest:
            f.write(json.dumps(row) + "\n")

    return {
        "manifest_path": str(manifest_path),
        "sheet_count": math.ceil(len(images) / tiles_per_sheet),
        "tile_count": len(manifest),
        "sheets": [f"sheet-{i:03d}.jpg" for i in range(math.ceil(len(images) / tiles_per_sheet))],
    }


def main():
    parser = argparse.ArgumentParser(description="Build contact sheets for intake overview.")
    parser.add_argument("--input_dir", required=False)
    parser.add_argument("--pdf", required=False)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--image_format", default="jpeg", choices=["jpeg", "png"])
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--out", required=False, help="Optional path to write manifest for driver stamping")
    parser.add_argument("--max_width", type=int, default=200)
    parser.add_argument("--grid_cols", type=int, default=5)
    parser.add_argument("--grid_rows", type=int, default=4)
    parser.add_argument("--pad", type=int, default=10)
    parser.add_argument("--number_overlay", action="store_true", help="Enable numbering overlays on tiles")
    parser.add_argument("--no-number-overlay", action="store_true", help="Disable numbering overlays on tiles")
    args, _unknown = parser.parse_known_args()

    ensure_dir(args.output_dir)

    images_dir = args.input_dir
    if not images_dir:
        if not args.pdf:
            raise SystemExit("Must provide --input_dir or --pdf")
        images_dir = str(Path(args.output_dir) / "rendered_pages")
        render_pdf_to_images(Path(args.pdf), Path(images_dir), args.dpi, args.image_format)

    result = make_contact_sheets(
        Path(images_dir),
        Path(args.output_dir),
        max_width=args.max_width,
        grid_cols=args.grid_cols,
        grid_rows=args.grid_rows,
        pad=args.pad,
        number_overlay=False if args.no_number_overlay else True,
    )
    if args.out:
        # write a manifest copy for driver stamping
        manifest_src = Path(result["manifest_path"])
        ensure_dir(Path(args.out).parent)
        manifest_src.replace(Path(args.out)) if manifest_src != Path(args.out) else None
        result["manifest_path"] = str(args.out)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
