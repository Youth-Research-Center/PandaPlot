#!/usr/bin/env python3
"""Build installer executable for PandaPlot using pyside6-deploy."""

import argparse
import configparser
import shutil
import subprocess
import sys
from pathlib import Path


def _expected_exe_format(mode: str) -> str:
    """Mirrors PySide6's deploy_lib.finalize(): the extension pyside6-deploy
    gives the final copied executable/bundle for each platform and mode."""
    if sys.platform == "win32":
        exe_format = ".exe"
    elif sys.platform == "darwin":
        exe_format = ".app"
    else:
        exe_format = ".bin"

    if mode == "standalone" and sys.platform != "darwin":
        exe_format = ".dist"
    return exe_format


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

    # pyside6-deploy resolves exec_directory relative to its own working
    # directory (not the spec's project_dir), then copies the final
    # executable there without creating it first, so a fresh clone fails
    # with FileNotFoundError on that copy. Resolve it the same way here,
    # against the same working directory we run the subprocess with below,
    # so the two stay in sync even if that working directory ever changes.
    build_cwd = repo_root
    spec_config = configparser.ConfigParser()
    spec_config.read(spec_path)
    exec_directory = spec_config.get("app", "exec_directory", fallback="deployment")
    (build_cwd / exec_directory).mkdir(parents=True, exist_ok=True)

    deploy_executable = shutil.which("pyside6-deploy")
    if deploy_executable:
        cmd = [deploy_executable, "-c", str(spec_path)]
    else:
        cmd = ["uv", "run", "pyside6-deploy", "-c", str(spec_path)]

    if args.dry_run:
        cmd.append("--dry-run")

    print(f"Running: {' '.join(cmd)} (cwd: {build_cwd})")
    result = subprocess.run(cmd, cwd=build_cwd, check=False)
    if result.returncode != 0:
        return result.returncode

    if args.dry_run:
        return 0

    # pyside6-deploy swallows Nuitka/deploy failures internally and always
    # exits 0 (see PySide6.scripts.deploy.main's bare `except Exception:
    # print(...)`), so a non-zero returncode above can't be relied on to
    # detect a failed build. Verify the expected output actually exists.
    title = spec_config.get("app", "title", fallback="app")
    mode = spec_config.get("nuitka", "mode", fallback="onefile")
    output_path = build_cwd / exec_directory / f"{title}{_expected_exe_format(mode)}"
    if not output_path.exists():
        print(
            f"Error: pyside6-deploy reported success but no output was produced at "
            f"{output_path}. Check the build log above for the underlying failure.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
