"""Tests for icon_bundle.cli and the build_icon_bundle.py launcher."""

import subprocess
import sys

from icon_bundle.cli import REPO_ROOT, run

from tests.scripts.icons.conftest import PHOSPHOR_LICENSE, fake_fetch, write_manifest

_LAUNCHER = REPO_ROOT / "scripts" / "icons" / "build_icon_bundle.py"


def test_run_writes_outputs_and_check_detects_drift(tmp_path):
    manifest_path = write_manifest(tmp_path)
    icons_dir = tmp_path / "icons"
    notices = tmp_path / "NOTICES.md"
    kwargs = {"icons_dir": icons_dir, "notices_path": notices, "fetch": fake_fetch}

    assert run(manifest_path, check=False, **kwargs) == 0
    assert (icons_dir / "icon_bundle.json").is_file()
    assert (icons_dir / "licenses" / "phosphor-LICENSE.txt").read_text(encoding="utf-8") == PHOSPHOR_LICENSE
    assert notices.is_file()
    assert run(manifest_path, check=True, **kwargs) == 0

    (icons_dir / "icon_bundle.json").write_text("{}", encoding="utf-8")
    assert run(manifest_path, check=True, **kwargs) == 1


def test_run_removes_licence_files_of_sources_no_longer_used(tmp_path):
    manifest_path = write_manifest(tmp_path)
    icons_dir = tmp_path / "icons"
    (icons_dir / "licenses").mkdir(parents=True)
    stale = icons_dir / "licenses" / "lucide-LICENSE.txt"
    stale.write_text("old", encoding="utf-8")
    kwargs = {"icons_dir": icons_dir, "notices_path": tmp_path / "N.md", "fetch": fake_fetch}

    assert run(manifest_path, check=True, **kwargs) == 1
    assert run(manifest_path, check=False, **kwargs) == 0

    assert not stale.exists()


def test_repo_root_resolves_to_the_repository_root():
    assert (REPO_ROOT / "pyproject.toml").is_file()
    assert (REPO_ROOT / "scripts" / "icons" / "icon_bundle").is_dir()


def test_launcher_runs_in_isolated_mode_without_the_script_directory_on_sys_path():
    result = subprocess.run(
        [sys.executable, "-I", str(_LAUNCHER), "--help"], capture_output=True, text=True, timeout=60, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert "--check" in result.stdout
