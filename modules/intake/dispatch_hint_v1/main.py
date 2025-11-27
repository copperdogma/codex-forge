import argparse
import json
from pathlib import Path

from modules.common.utils import ensure_dir


def main():
    parser = argparse.ArgumentParser(description="Write dispatch hint from confirmed intake plan")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.plan, "r", encoding="utf-8") as f:
        plan = json.load(f)
    hint = {
        "recommended_recipe": plan.get("recommended_recipe"),
        "plan_path": args.plan,
        "capability_gaps": plan.get("capability_gaps", []),
        "warnings": plan.get("warnings", []),
    }
    ensure_dir(Path(args.out).parent)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(hint, f, ensure_ascii=False, indent=2)
    print(json.dumps(hint, indent=2))


if __name__ == "__main__":
    main()
