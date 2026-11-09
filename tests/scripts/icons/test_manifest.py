"""Tests for icon_bundle.manifest."""

import pytest
from icon_bundle.manifest import load_manifest

from tests.scripts.icons.conftest import write_manifest


def test_load_manifest_reads_sources_icons_and_overrides(tmp_path):
    path = write_manifest(tmp_path, icons='["folder", "mountains"]', overrides='mountains = "lucide:mountain"')

    manifest = load_manifest(path)

    assert manifest.weights == ("regular",)
    assert manifest.icons == ("folder", "mountains")
    assert manifest.sources["phosphor"].package == "@phosphor-icons/core"
    assert manifest.sources["lucide"].title == "Lucide"
    assert manifest.overrides == {"mountains": ("lucide", "mountain")}


def test_load_manifest_rejects_unknown_weight(tmp_path):
    with pytest.raises(ValueError, match="weight"):
        load_manifest(write_manifest(tmp_path, weights='["regular", "chunky"]'))


def test_load_manifest_rejects_duplicate_icons(tmp_path):
    with pytest.raises(ValueError, match="Duplicate"):
        load_manifest(write_manifest(tmp_path, icons='["folder", "folder"]'))


def test_load_manifest_rejects_override_for_unlisted_icon(tmp_path):
    with pytest.raises(ValueError, match="not listed"):
        load_manifest(write_manifest(tmp_path, overrides='mountains = "lucide:mountain"'))


def test_load_manifest_rejects_override_from_undeclared_source(tmp_path):
    path = write_manifest(tmp_path, icons='["mountains"]', overrides='mountains = "feather:mountain"')

    with pytest.raises(ValueError, match="feather"):
        load_manifest(path)
