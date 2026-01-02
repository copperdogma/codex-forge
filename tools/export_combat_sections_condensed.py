import argparse
import json
from pathlib import Path


def load_gamebook(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def extract_html(section: dict) -> str:
    if "presentation_html" in section and section["presentation_html"]:
        return section["presentation_html"]
    if "html" in section and section["html"]:
        return section["html"]
    if "raw_html" in section and section["raw_html"]:
        return section["raw_html"]
    return ""


def extract_combats(section: dict):
    combats = []
    for idx, ev in enumerate(section.get("sequence") or []):
        if ev.get("kind") == "combat":
            combats.append({"index": idx, "combat": ev})
    return combats


def main() -> int:
    ap = argparse.ArgumentParser(description="Export condensed combat sections (section_id, combat, html).")
    ap.add_argument("--gamebook", required=True, help="Path to gamebook.json")
    ap.add_argument("--out", required=True, help="Output JSONL path")
    args = ap.parse_args()

    gamebook_path = Path(args.gamebook)
    out_path = Path(args.out)

    gamebook = load_gamebook(gamebook_path)
    sections = gamebook.get("sections") or {}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w") as f:
        for sid, sec in sections.items():
            combats = extract_combats(sec)
            if not combats:
                continue
            row = {
                "section_id": sid,
                "combat": combats,
                "html": extract_html(sec),
            }
            f.write(json.dumps(row, ensure_ascii=True) + "\n")
            count += 1

    print(f"Wrote {count} condensed combat sections to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
