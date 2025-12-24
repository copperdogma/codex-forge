import argparse
import os
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, ProgressLogger


BLOCK_TAGS = {"h1", "h2", "p", "dt", "dd", "li", "caption", "th", "td", "img", "a"}
CONTAINER_TAGS = {"table", "thead", "tbody", "tr", "ol", "ul", "dl"}


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class HtmlBlockParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks: List[Dict[str, Any]] = []
        self._current: Optional[Dict[str, Any]] = None
        self._order = 0

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag not in BLOCK_TAGS and tag not in CONTAINER_TAGS:
            return

        if self._current is not None and tag in BLOCK_TAGS and tag not in {"table", "img"}:
            self._flush_current()

        if tag == "img":
            alt = ""
            for k, v in attrs:
                if k.lower() == "alt":
                    alt = v or ""
                    break
            self._order += 1
            self.blocks.append({
                "block_type": "img",
                "text": alt,
                "order": self._order,
                "attrs": {"alt": alt},
            })
            return

        if tag in CONTAINER_TAGS:
            self._order += 1
            self.blocks.append({
                "block_type": tag,
                "text": "",
                "order": self._order,
                "attrs": None,
            })
            return

        if tag in BLOCK_TAGS:
            attrs_dict: Dict[str, Any] = {}
            if tag == "p":
                for k, v in attrs:
                    if k.lower() == "class" and v:
                        attrs_dict["class"] = v
                        break
            elif tag == "a":
                for k, v in attrs:
                    if k.lower() == "href" and v:
                        attrs_dict["href"] = v
                        break
            self._current = {
                "block_type": tag,
                "text_parts": [],
                "order": None,
                "attrs": attrs_dict or None,
            }

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if self._current and self._current.get("block_type") == tag:
            self._flush_current()
        if tag == "p" and not self._current:
            if self.blocks and self.blocks[-1]["block_type"] == "p" and not self.blocks[-1].get("text"):
                return
        if tag in BLOCK_TAGS or tag in CONTAINER_TAGS:
            self._order += 1
            self.blocks.append({
                "block_type": f"/{tag}",
                "text": "",
                "order": self._order,
                "attrs": None,
            })

    def handle_data(self, data: str):
        if self._current is not None and data:
            self._current["text_parts"].append(data)

    def _flush_current(self):
        if not self._current:
            return
        tag = self._current.get("block_type")
        self._order += 1
        text = _normalize_text(" ".join(self._current.get("text_parts", [])))
        self.blocks.append({
            "block_type": tag,
            "text": text,
            "order": self._order,
            "attrs": self._current.get("attrs"),
        })
        self._current = None

    def close(self):
        super().close()
        if self._current:
            self._flush_current()


def parse_blocks(html: str, drop_empty: bool) -> List[Dict[str, Any]]:
    parser = HtmlBlockParser()
    parser.feed(html or "")
    parser.close()
    blocks = parser.blocks
    if not drop_empty:
        return blocks
    filtered: List[Dict[str, Any]] = []
    for block in blocks:
        block_type = block["block_type"]
        if block_type.startswith("/") or block_type in CONTAINER_TAGS or block_type == "img":
            filtered.append(block)
            continue
        if block.get("text"):
            filtered.append(block)
    # Re-number order to keep a contiguous sequence after filtering.
    renumbered: List[Dict[str, Any]] = []
    for idx, block in enumerate(filtered, start=1):
        new_block = dict(block)
        new_block["order"] = idx
        renumbered.append(new_block)
    return renumbered


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse per-page HTML into ordered blocks.")
    parser.add_argument("--inputs", nargs="*", help="Driver-provided inputs")
    parser.add_argument("--pages", help="Path to page_html_v1 JSONL")
    parser.add_argument("--outdir", help="Output directory")
    parser.add_argument("--out", default="page_blocks.jsonl", help="Output JSONL filename")
    parser.add_argument("--drop-empty-blocks", dest="drop_empty_blocks", action="store_true")
    parser.add_argument("--drop_empty_blocks", dest="drop_empty_blocks", action="store_true")
    parser.add_argument("--keep-empty-blocks", dest="drop_empty_blocks", action="store_false")
    parser.add_argument("--keep_empty_blocks", dest="drop_empty_blocks", action="store_false")
    parser.set_defaults(drop_empty_blocks=True)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    pages_path = args.pages or (args.inputs[0] if args.inputs else None)
    if not pages_path:
        raise SystemExit("Missing --pages or --inputs")
    if not os.path.exists(pages_path):
        raise SystemExit(f"Missing pages file: {pages_path}")

    if not args.outdir:
        args.outdir = str(Path(pages_path).parent)
    ensure_dir(args.outdir)
    if os.path.isabs(args.out) or os.sep in args.out:
        out_path = args.out
    else:
        out_path = os.path.join(args.outdir, args.out)

    rows = list(read_jsonl(pages_path))
    total = len(rows)
    if total == 0:
        raise SystemExit(f"Input is empty: {pages_path}")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log(
        "adapter",
        "running",
        current=0,
        total=total,
        message="Parsing HTML blocks",
        artifact=out_path,
        module_id="html_to_blocks_v1",
        schema_version="page_html_blocks_v1",
    )

    out_rows: List[Dict[str, Any]] = []
    for idx, page in enumerate(rows, start=1):
        blocks = parse_blocks(page.get("html") or "", drop_empty=args.drop_empty_blocks)
        is_blank = len(blocks) == 0
        out_rows.append({
            "schema_version": "page_html_blocks_v1",
            "module_id": "html_to_blocks_v1",
            "run_id": args.run_id,
            "created_at": _utc(),
            "page": page.get("page"),
            "page_number": page.get("page_number"),
            "original_page_number": page.get("original_page_number"),
            "image": page.get("image"),
            "spread_side": page.get("spread_side"),
            "is_blank": is_blank,
            "blocks": blocks,
        })
        logger.log(
            "adapter",
            "running",
            current=idx,
            total=total,
            message=f"Parsed page {page.get('page_number')}",
            artifact=out_path,
            module_id="html_to_blocks_v1",
            schema_version="page_html_blocks_v1",
        )

    save_jsonl(out_path, out_rows)
    total_blocks = sum(len(row.get("blocks", [])) for row in out_rows)
    # Determine stage name based on output filename (html_blocks_raw vs html_blocks_repaired)
    stage_name = "html_blocks_repaired" if "repaired" in str(out_path) else "html_blocks_raw"
    logger.log(
        stage_name,
        "done",
        current=total,
        total=total,
        message=f"HTML→blocks complete: {total} pages, {total_blocks} blocks",
        artifact=out_path,
        module_id="html_to_blocks_v1",
        schema_version="page_html_blocks_v1",
        extra={"summary_metrics": {"pages_count": total, "blocks_count": total_blocks}},
    )


if __name__ == "__main__":
    main()
