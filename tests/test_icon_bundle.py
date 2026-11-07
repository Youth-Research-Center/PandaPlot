"""The committed icon bundle must stay in sync with its manifest (offline check, no downloads)."""

import importlib.util
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "icons" / "build_icon_bundle.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("build_icon_bundle", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def manifest(script):
    return script.load_manifest(script.MANIFEST_PATH)


@pytest.fixture(scope="module")
def bundle(script):
    return json.loads((script.ICONS_DIR / script.BUNDLE_NAME).read_text(encoding="utf-8"))


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


def test_every_used_source_ships_its_licence_and_is_named_in_the_notices(script, bundle):
    notices = script.NOTICES_PATH.read_text(encoding="utf-8")
    for name, meta in bundle["sources"].items():
        licence = script.ICONS_DIR / "licenses" / f"{name}-LICENSE.txt"
        assert licence.is_file() and "Copyright" in licence.read_text(encoding="utf-8")
        assert meta["title"] in notices
        assert f"licenses/{name}-LICENSE.txt" in notices


def test_committed_notices_match_the_generated_notices_exactly(script, bundle):
    licences = {
        name: (script.ICONS_DIR / "licenses" / f"{name}-LICENSE.txt").read_text(encoding="utf-8")
        for name in bundle["sources"]
    }

    assert script.NOTICES_PATH.read_text(encoding="utf-8") == script.render_notices(bundle, licences)


def test_icon_sources_reference_declared_sources(bundle):
    for name, entry in bundle["icons"].items():
        assert entry["source"] in bundle["sources"], name
