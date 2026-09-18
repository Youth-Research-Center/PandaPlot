"""Tests for scripts/build_installer.py's own logic (not pyside6-deploy itself)."""

import configparser
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "build_installer.py"


def _load_build_installer():
    spec = importlib.util.spec_from_file_location("build_installer", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def build_installer():
    return _load_build_installer()


def test_main_creates_configured_exec_directory(tmp_path, build_installer, monkeypatch):
    """pyside6-deploy copies the built executable into exec_directory but never
    creates it, so main() must create it upfront (see the regression this
    was added to fix: a clean checkout's first build failed with
    FileNotFoundError on that copy)."""
    spec_path = tmp_path / "pysidedeploy.spec"
    spec_config = configparser.ConfigParser()
    spec_config["app"] = {"exec_directory": "custom_output"}
    with open(spec_path, "w") as f:
        spec_config.write(f)

    # main() derives repo_root from __file__, so point it at tmp_path.
    monkeypatch.setattr(build_installer, "__file__", str(tmp_path / "scripts" / "build_installer.py"))
    monkeypatch.setattr(sys, "argv", ["build_installer.py", "--spec", str(spec_path)])

    with patch.object(build_installer.subprocess, "run", return_value=MagicMock(returncode=0)):
        build_installer.main()

    assert (tmp_path / "custom_output").is_dir()


def test_main_defaults_to_deployment_when_exec_directory_unset(tmp_path, build_installer, monkeypatch):
    """exec_directory is an optional spec field; fall back to 'deployment' to
    match pysidedeploy.spec's own default when it's missing."""
    spec_path = tmp_path / "pysidedeploy.spec"
    spec_config = configparser.ConfigParser()
    spec_config["app"] = {}
    with open(spec_path, "w") as f:
        spec_config.write(f)

    monkeypatch.setattr(build_installer, "__file__", str(tmp_path / "scripts" / "build_installer.py"))
    monkeypatch.setattr(sys, "argv", ["build_installer.py", "--spec", str(spec_path)])

    with patch.object(build_installer.subprocess, "run", return_value=MagicMock(returncode=0)):
        build_installer.main()

    assert (tmp_path / "deployment").is_dir()
