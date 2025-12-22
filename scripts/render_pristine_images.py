import argparse
from pathlib import Path
from PIL import Image
from modules.common.ocr import render_pdf


def main() -> None:
    parser = argparse.ArgumentParser(description="Render pristine PDF pages to images in batches.")
    parser.add_argument("--pdf", required=True, help="Path to PDF")
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument("--dpi", type=int, default=300, help="Render DPI")
    parser.add_argument("--start", type=int, default=1, help="Start page (1-based)")
    parser.add_argument("--end", type=int, default=None, help="End page (1-based)")
    parser.add_argument("--batch", type=int, default=5, help="Pages per batch")
    args = parser.parse_args()

    Image.MAX_IMAGE_PIXELS = None

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.end is None:
        raise SystemExit("--end is required for batching; provide the last page number")

    for s in range(args.start, args.end + 1, args.batch):
        e = min(args.end, s + args.batch - 1)
        print(f"rendering pages {s}-{e}")
        render_pdf(args.pdf, str(out_dir), dpi=args.dpi, start_page=s, end_page=e)

    print("done")


if __name__ == "__main__":
    main()
