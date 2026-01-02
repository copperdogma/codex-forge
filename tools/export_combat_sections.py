import argparse
import json
from pathlib import Path


def load_gamebook(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def has_combat(section: dict) -> bool:
    for ev in section.get("sequence") or []:
        if ev.get("kind") == "combat":
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Export full section nodes that contain combat events.")
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
            if not has_combat(sec):
                continue
            row = {
                "section_id": sid,
                "section": sec,
            }
            f.write(json.dumps(row, ensure_ascii=True) + "\n")
            count += 1

    print(f"Wrote {count} combat sections to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
