"""Tests for pysidedeploy.spec deployment configuration."""

import configparser
import shutil
import subprocess
from pathlib import Path

import pytest


def test_pysidedeploy_spec_exists():
    """Verify that pysidedeploy.spec exists at root directory."""
    spec_path = Path("pysidedeploy.spec")
    assert spec_path.is_file(), "pysidedeploy.spec file is missing from project root"


def test_pysidedeploy_spec_contents():
    """Verify key configuration options in pysidedeploy.spec."""
    spec_path = Path("pysidedeploy.spec")
    parser = configparser.ConfigParser()
    parser.read(spec_path)

    assert parser.has_section("app")
    assert parser.get("app", "title") == "PandaPlot"
    assert parser.get("app", "input_file") == "pandaplot/app.py"
    assert parser.get("app", "project_file") == "pyproject.toml"

    assert parser.has_section("qt")
    modules = [m.strip() for m in parser.get("qt", "modules").split(",")]
    for expected_mod in ("Core", "Gui", "Widgets"):
        assert expected_mod in modules


def test_pyside6_deploy_dry_run():
    """Verify that pyside6-deploy dry run succeeds without errors or missing module warnings."""
    deploy_executable = shutil.which("pyside6-deploy")
    if deploy_executable:
        cmd = [deploy_executable, "-c", "pysidedeploy.spec", "--dry-run"]
    elif shutil.which("uv"):
        cmd = ["uv", "run", "pyside6-deploy", "-c", "pysidedeploy.spec", "--dry-run"]
    else:
        pytest.skip("Neither pyside6-deploy nor uv is available on PATH")

    repo_root = Path(__file__).resolve().parent.parent
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=repo_root,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as err:
        pytest.fail(f"pyside6-deploy execution failed: {err}")

    assert result.returncode == 0, f"pyside6-deploy dry-run failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert "WARNING:root:[DEPLOY] Found 'import PySide6'" not in result.stderr
    assert "WARNING:root:[DEPLOY] Unable to resolve a valid project file" not in result.stderr
