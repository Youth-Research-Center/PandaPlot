#!/usr/bin/env python3
"""Build installer executable for PandaPlot using pyside6-deploy."""

import argparse
import configparser
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build PandaPlot desktop executable installer using pyside6-deploy."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run to inspect deploy commands without compiling.",
    )
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("pysidedeploy.spec"),
        help="Path to the deployment spec file (default: pysidedeploy.spec).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    spec_path = args.spec if args.spec.is_absolute() else (repo_root / args.spec).resolve()

    if not spec_path.is_file():
        print(f"Error: Deployment spec file not found at {spec_path}", file=sys.stderr)
        return 1

    # pyside6-deploy copies the final executable into exec_directory but never
    # creates it, so a fresh clone fails with FileNotFoundError on that copy.
    spec_config = configparser.ConfigParser()
    spec_config.read(spec_path)
    exec_directory = spec_config.get("app", "exec_directory", fallback="deployment")
    (repo_root / exec_directory).mkdir(parents=True, exist_ok=True)

    deploy_executable = shutil.which("pyside6-deploy")
    if deploy_executable:
        cmd = [deploy_executable, "-c", str(spec_path)]
    else:
        cmd = ["uv", "run", "pyside6-deploy", "-c", str(spec_path)]

    if args.dry_run:
        cmd.append("--dry-run")

    print(f"Running: {' '.join(cmd)} (cwd: {repo_root})")
    result = subprocess.run(cmd, cwd=repo_root)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
