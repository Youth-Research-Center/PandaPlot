"""The committed icon bundle must stay in sync with its manifest (offline check, no downloads)."""

import json

import pytest
from icon_bundle.cli import BUNDLE_NAME, ICONS_DIR, MANIFEST_PATH, NOTICES_PATH
from icon_bundle.manifest import load_manifest
from icon_bundle.notices import render_notices


@pytest.fixture(scope="module")
def manifest():
    return load_manifest(MANIFEST_PATH)


@pytest.fixture(scope="module")
def bundle():
    return json.loads((ICONS_DIR / BUNDLE_NAME).read_text(encoding="utf-8"))


def test_bundle_contains_every_manifest_icon_in_every_weight(manifest, bundle):
    assert set(bundle["icons"]) == set(manifest.icons)
    for name, entry in bundle["icons"].items():
        assert set(entry["weights"]) == set(manifest.weights), name


def test_bundle_svgs_can_be_tinted(bundle):
    for name, entry in bundle["icons"].items():
        for weight, svg in entry["weights"].items():
            assert svg.startswith("<svg") and "currentColor" in svg, f"{name}/{weight}"


def test_bundle_records_the_pinned_source_versions(manifest, bundle):
    for name, meta in bundle["sources"].items():
        assert meta["version"] == manifest.sources[name].version
        assert meta["license"] == manifest.sources[name].license


def test_every_used_source_ships_its_licence_and_is_named_in_the_notices(bundle):
    notices = NOTICES_PATH.read_text(encoding="utf-8")
    for name, meta in bundle["sources"].items():
        licence = ICONS_DIR / "licenses" / f"{name}-LICENSE.txt"
        assert licence.is_file() and "Copyright" in licence.read_text(encoding="utf-8")
        assert meta["title"] in notices
        assert f"licenses/{name}-LICENSE.txt" in notices


def test_committed_notices_match_the_generated_notices_exactly(bundle):
    licences = {
        name: (ICONS_DIR / "licenses" / f"{name}-LICENSE.txt").read_text(encoding="utf-8")
        for name in bundle["sources"]
    }

    assert NOTICES_PATH.read_text(encoding="utf-8") == render_notices(bundle, licences)


def test_icon_sources_reference_declared_sources(bundle):
    for name, entry in bundle["icons"].items():
        assert entry["source"] in bundle["sources"], name
