#!/usr/bin/env python3
"""Build installer executable for PandaPlot using pyside6-deploy."""

import argparse
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

    deploy_executable = shutil.which("pyside6-deploy")
    if deploy_executable:
        cmd = [deploy_executable, "-c", str(args.spec)]
    else:
        cmd = ["uv", "run", "pyside6-deploy", "-c", str(args.spec)]

    if args.dry_run:
        cmd.append("--dry-run")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
