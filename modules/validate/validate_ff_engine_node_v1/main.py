import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict

from modules.common.utils import ProgressLogger


def ensure_ajv(node_bin: str, validator_dir: str):
    """Preflight check that ajv is available."""
    cmd = [node_bin, "-e", "require('ajv')"]
    proc = subprocess.run(cmd, cwd=validator_dir, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        raise RuntimeError(
            "ajv is not installed for the FF validator. "
            f"Run `npm install ajv` in {validator_dir}. "
            f"Details: {stderr or proc.stdout}"
        )


def run_node_validator(node_bin: str, validator_dir: str, gamebook: str) -> Dict[str, Any]:
    cli_path = os.path.join(validator_dir, "cli-validator.js")
    if not os.path.exists(cli_path):
        raise FileNotFoundError(f"cli-validator.js not found at {cli_path}")

    cmd = [node_bin, cli_path, gamebook, "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    if not stdout:
        raise RuntimeError(f"Validator produced no output. Stderr: {stderr}")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse validator JSON output: {exc}\nstdout:\n{stdout}\nstderr:\n{stderr}") from exc

    data["_exit_code"] = proc.returncode
    data["_stderr"] = stderr
    return data


def main():
    parser = argparse.ArgumentParser(description="Validate gamebook.json using the official FF Engine validator (Node/Ajv).")
    parser.add_argument("--input", required=True, help="Path to gamebook.json")
    parser.add_argument("--out", required=True, help="Path to write validation report JSON")
    parser.add_argument("--validator_dir", default=os.path.join(os.path.dirname(__file__), "validator"),
                        help="Directory containing cli-validator.js (bundled)")
    parser.add_argument("--node_bin", default="node", help="Node executable to use")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    # Node version check (>=18)
    ver_proc = subprocess.run([args.node_bin, "-e", "console.log(process.versions.node)"],
                              capture_output=True, text=True)
    if ver_proc.returncode != 0:
        raise RuntimeError(f"Unable to determine node version: {ver_proc.stderr}")
    ver_str = ver_proc.stdout.strip()
    major = int(ver_str.split(".")[0]) if ver_str else 0
    if major < 18:
        raise SystemExit(f"Node {ver_str} is too old; require >=18 for the FF validator.")
    logger.log("validate_ff_engine_node", "running", message="Checking ajv and invoking Node validator", module_id="validate_ff_engine_node_v1")

    ensure_ajv(args.node_bin, args.validator_dir)

    bundle_script = os.path.join(args.validator_dir, "build_bundle.js")
    if os.path.exists(bundle_script):
        bundle_proc = subprocess.run([args.node_bin, bundle_script], cwd=args.validator_dir, capture_output=True, text=True)
        if bundle_proc.returncode != 0:
            raise RuntimeError(
                "Failed to regenerate validator bundle. "
                f"stdout: {bundle_proc.stdout.strip()} stderr: {bundle_proc.stderr.strip()}"
            )

    report = run_node_validator(args.node_bin, args.validator_dir, args.input)
    report["validator_dir"] = args.validator_dir

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    if not report.get("valid", False) or report.get("_exit_code", 0) != 0:
        logger.log("validate_ff_engine_node", "failed", message=f"Validation failed ({len(report.get('errors', []))} errors)", module_id="validate_ff_engine_node_v1", artifact=args.out)
        print(f"Validation failed via Node validator; report → {args.out}")
        sys.exit(1)

    logger.log("validate_ff_engine_node", "done", message=f"Valid gamebook ({report.get('summary', {}).get('totalSections', 'n/a')} sections)", module_id="validate_ff_engine_node_v1", artifact=args.out)
    print(f"Validation passed via Node validator; report → {args.out}")


if __name__ == "__main__":
    main()
