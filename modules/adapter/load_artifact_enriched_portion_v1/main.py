import argparse
import os
import shutil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--out")
    parser.add_argument("--outdir")
    parser.add_argument("--schema-version", dest="schema_version")
    parser.add_argument("--schema_version", dest="schema_version")
    parser.add_argument("--run-id")
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    args, _unknown = parser.parse_known_args()

    out_path = args.out
    if out_path and args.outdir and not os.path.isabs(out_path):
        out_path = os.path.join(args.outdir, out_path)

    if not out_path and args.outdir:
        out_path = os.path.join(args.outdir, os.path.basename(args.path))

    if not out_path:
        raise ValueError("Either --out or --outdir must be provided")

    if not os.path.exists(args.path):
        raise FileNotFoundError(f"Source artifact not found: {args.path}")

    if os.path.abspath(args.path) != os.path.abspath(out_path):
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        shutil.copy2(args.path, out_path)
        print(f"Copied {args.path} to {out_path}")
    else:
        print(f"Artifact already at {out_path}")


if __name__ == "__main__":
    main()
