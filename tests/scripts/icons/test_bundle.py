"""Tests for icon_bundle.bundle and icon_bundle.notices."""

import json

import pytest
from icon_bundle.bundle import build_bundle, dump_bundle
from icon_bundle.manifest import load_manifest
from icon_bundle.notices import render_notices

from tests.scripts.icons.conftest import FOLDER_SVG, LUCIDE_LICENSE, PHOSPHOR_LICENSE, fake_fetch, make_tarball, write_manifest


def test_build_bundle_collects_every_weight_and_the_licence(tmp_path):
    manifest = load_manifest(write_manifest(tmp_path, weights='["regular", "bold"]'))

    bundle = build_bundle(manifest, fake_fetch)

    folder = bundle.data["icons"]["folder"]
    assert folder["source"] == "phosphor"
    assert set(folder["weights"]) == {"regular", "bold"}
    assert "<!--" not in folder["weights"]["regular"]
    assert bundle.data["sources"]["phosphor"] == {
        "package": "@phosphor-icons/core", "title": "Phosphor Icons", "version": "2.1.1", "license": "MIT",
    }
    assert bundle.licenses["phosphor"] == PHOSPHOR_LICENSE
    assert "lucide" not in bundle.data["sources"]


def test_build_bundle_applies_override_from_second_source(tmp_path):
    path = write_manifest(tmp_path, icons='["folder", "mountains"]', overrides='mountains = "lucide:mountain"')
    manifest = load_manifest(path)

    bundle = build_bundle(manifest, fake_fetch)

    assert bundle.data["icons"]["mountains"]["source"] == "lucide"
    assert 'stroke="currentColor"' in bundle.data["icons"]["mountains"]["weights"]["regular"]
    assert bundle.data["icons"]["folder"]["source"] == "phosphor"
    assert set(bundle.data["sources"]) == {"phosphor", "lucide"}
    assert bundle.licenses["lucide"] == LUCIDE_LICENSE


def test_build_bundle_reports_all_missing_icons_at_once(tmp_path):
    manifest = load_manifest(write_manifest(tmp_path, icons='["folder", "nope", "also-nope"]'))

    with pytest.raises(ValueError) as error:
        build_bundle(manifest, fake_fetch)

    assert "nope" in str(error.value) and "also-nope" in str(error.value)


def test_build_bundle_normalises_licence_line_endings(tmp_path):
    crlf_tar = make_tarball({"LICENSE": "MIT License\r\nCopyright (c) 2023 X\r\n", "assets/regular/folder.svg": FOLDER_SVG})
    manifest = load_manifest(write_manifest(tmp_path))

    bundle = build_bundle(manifest, lambda source: crlf_tar)

    assert "\r" not in bundle.licenses["phosphor"]


def test_render_notices_lists_copyright_and_icons_per_source(tmp_path):
    path = write_manifest(tmp_path, icons='["folder", "mountains"]', overrides='mountains = "lucide:mountain"')
    bundle = build_bundle(load_manifest(path), fake_fetch)

    notices = render_notices(bundle.data, bundle.licenses)

    assert "Phosphor Icons 2.1.1" in notices
    assert "Copyright (c) 2023 Phosphor Icons" in notices
    assert "Copyright (c) 2026 Lucide Icons and Contributors" in notices
    assert "folder" in notices and "mountains" in notices
    assert "licenses/phosphor-LICENSE.txt" in notices


def test_dump_bundle_is_deterministic_json(tmp_path):
    bundle = build_bundle(load_manifest(write_manifest(tmp_path)), fake_fetch)

    text = dump_bundle(bundle.data)

    assert text == dump_bundle(json.loads(text))
    assert text.endswith("\n")
