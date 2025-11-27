import math
import os
from pathlib import Path
from typing import List, Dict, Any
from PIL import Image, ImageDraw, ImageFont
import json
import argparse

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
    images = sorted([p for p in input_dir.iterdir() if p.suffix.lower() in {'.jpg', '.jpeg', '.png'}])
    tiles_per_sheet = grid_cols * grid_rows
    manifest: List[Dict[str, Any]] = []
    font = load_font(18)

    for sheet_idx in range(math.ceil(len(images) / tiles_per_sheet)):
        sheet_images = images[sheet_idx * tiles_per_sheet : (sheet_idx + 1) * tiles_per_sheet]
        thumbs = []
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
            thumbs.append((path, thumb))

        max_h = max(t[1].height for t in thumbs) if thumbs else 0
        sheet_w = grid_cols * max_width + (grid_cols + 1) * pad
        sheet_h = grid_rows * max_h + (grid_rows + 1) * pad
        sheet = Image.new("RGB", (sheet_w, sheet_h), color=(245, 245, 245))

        for local_idx, (path, thumb) in enumerate(thumbs):
            row = local_idx // grid_cols
            col = local_idx % grid_cols
            x = pad + col * (max_width + pad)
            y = pad + row * (max_h + pad)
            sheet.paste(thumb, (x, y))
            manifest.append(
                {
                    "sheet_id": f"sheet-{sheet_idx:03d}",
                    "tile_index": local_idx,
                    "source_image": path.name,
                    "display_number": sheet_idx * tiles_per_sheet + local_idx + 1,
                    "sheet_path": str(output_dir / f"sheet-{sheet_idx:03d}.jpg"),
                    "tile_bbox": {"x": x, "y": y, "width": thumb.width, "height": thumb.height},
                    "orig_size": {"width": im.size[0], "height": im.size[1]},
                    "schema_version": "contact_sheet_manifest_v1",
                }
            )
        sheet_path = output_dir / f"sheet-{sheet_idx:03d}.jpg"
        sheet.save(sheet_path, quality=85)
    manifest_path = output_dir / "contact_sheet_manifest.jsonl"
    with manifest_path.open("w") as f:
        for row in manifest:
            f.write(json.dumps(row) + "\n")
    return {
        "manifest_path": str(manifest_path),
        "sheet_count": math.ceil(len(images) / tiles_per_sheet),
        "tile_count": len(manifest),
        "sheets": [f"sheet-{i:03d}.jpg" for i in range(math.ceil(len(images) / tiles_per_sheet))],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--max_width", type=int, default=200)
    parser.add_argument("--grid_cols", type=int, default=5)
    parser.add_argument("--grid_rows", type=int, default=4)
    args = parser.parse_args()
    result = make_contact_sheets(
        Path(args.input_dir), Path(args.output_dir),
        max_width=args.max_width,
        grid_cols=args.grid_cols,
        grid_rows=args.grid_rows,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
