"""Regression tests for the crash-safe xdist scheduler."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FILE_COUNT = 30


def _run_inner_suite(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Run a small xdist suite in which one test kills its worker.

    Args:
        tmp_path: Directory to build the inner suite in.

    Returns:
        The finished process.
    """
    suite = tmp_path / "suite"
    suite.mkdir()
    for index in range(FILE_COUNT):
        (suite / f"test_f{index:02d}.py").write_text("import time\n\n\ndef test_q():\n    time.sleep(0.05)\n")
    (suite / "test_f15crash.py").write_text("import os\nimport time\n\n\ndef test_crash():\n    time.sleep(0.5)\n    os._exit(1)\n")
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    # Without the crash-safe plugin this run hangs, so the timeout turns a regression into a failure.
    command = [sys.executable, "-m", "pytest", str(suite), "-q", "-p", "no:cacheprovider", "-p", "tests.xdist_crash_safe"]
    command += ["-o", "addopts=", "-c", str(tmp_path / "pytest.ini"), "--rootdir", str(tmp_path)]
    command += ["-n", "2", "--dist=loadfile", "--max-worker-restart=1"]
    try:
        return subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, timeout=90, check=False)
    except subprocess.TimeoutExpired:
        pytest.fail("inner xdist run hung after a worker crash (the scheduler deadlocked)")


def test_worker_crash_neither_hangs_nor_reruns_the_crashed_test(tmp_path: Path) -> None:
    """A crashed worker is reported once, and the rest of the run still finishes."""
    result = _run_inner_suite(tmp_path)
    output = result.stdout + result.stderr

    assert re.search(rf"\b1 failed, {FILE_COUNT} passed\b", output), output
    assert output.count("crashed while running") == 1, output
