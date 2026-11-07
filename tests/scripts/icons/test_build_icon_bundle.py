"""Tests for scripts/icons/build_icon_bundle.py (offline: upstream tarballs are built in memory)."""

import base64
import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "icons" / "build_icon_bundle.py"

PHOSPHOR_LICENSE = "MIT License\n\nCopyright (c) 2023 Phosphor Icons\n\nPermission is hereby granted...\n"
LUCIDE_LICENSE = "ISC License\n\nCopyright (c) 2026 Lucide Icons and Contributors\n"
FOLDER_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><!-- c --><path d="M0 0h8v8z"/></svg>'
MOUNTAIN_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor"><path d="m8 3 4 8"/></svg>'
)


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("build_icon_bundle", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_tarball(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, text in files.items():
            payload = text.encode("utf-8")
            info = tarfile.TarInfo(f"package/{name}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def integrity_of(data: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")


PHOSPHOR_TAR = make_tarball(
    {
        "LICENSE": PHOSPHOR_LICENSE,
        "assets/regular/folder.svg": FOLDER_SVG,
        "assets/bold/folder-bold.svg": FOLDER_SVG,
        "assets/regular/mountains.svg": FOLDER_SVG,
        "assets/bold/mountains-bold.svg": FOLDER_SVG,
    }
)
LUCIDE_TAR = make_tarball({"LICENSE": LUCIDE_LICENSE, "icons/mountain.svg": MOUNTAIN_SVG})


def write_manifest(tmp_path: Path, *, weights: str = '["regular"]', icons: str = '["folder"]', overrides: str = "") -> Path:
    text = f"""
weights = {weights}
icons = {icons}

[sources.phosphor]
package = "@phosphor-icons/core"
title = "Phosphor Icons"
version = "2.1.1"
integrity = "{integrity_of(PHOSPHOR_TAR)}"
license = "MIT"

[sources.lucide]
package = "lucide-static"
title = "Lucide"
version = "1.64.0"
integrity = "{integrity_of(LUCIDE_TAR)}"
license = "ISC"

[overrides]
{overrides}
"""
    path = tmp_path / "icon_manifest.toml"
    path.write_text(text, encoding="utf-8")
    return path


def fake_fetch(source):
    return {"phosphor": PHOSPHOR_TAR, "lucide": LUCIDE_TAR}[source.name]


# --- manifest -----------------------------------------------------------------------------------


def test_load_manifest_reads_sources_icons_and_overrides(mod, tmp_path):
    path = write_manifest(tmp_path, icons='["folder", "mountains"]', overrides='mountains = "lucide:mountain"')

    manifest = mod.load_manifest(path)

    assert manifest.weights == ("regular",)
    assert manifest.icons == ("folder", "mountains")
    assert manifest.sources["phosphor"].package == "@phosphor-icons/core"
    assert manifest.sources["lucide"].title == "Lucide"
    assert manifest.overrides == {"mountains": ("lucide", "mountain")}


def test_load_manifest_rejects_unknown_weight(mod, tmp_path):
    with pytest.raises(ValueError, match="weight"):
        mod.load_manifest(write_manifest(tmp_path, weights='["regular", "chunky"]'))


def test_load_manifest_rejects_duplicate_icons(mod, tmp_path):
    with pytest.raises(ValueError, match="Duplicate"):
        mod.load_manifest(write_manifest(tmp_path, icons='["folder", "folder"]'))


def test_load_manifest_rejects_override_for_unlisted_icon(mod, tmp_path):
    with pytest.raises(ValueError, match="not listed"):
        mod.load_manifest(write_manifest(tmp_path, overrides='mountains = "lucide:mountain"'))


def test_load_manifest_rejects_override_from_undeclared_source(mod, tmp_path):
    path = write_manifest(tmp_path, icons='["mountains"]', overrides='mountains = "feather:mountain"')

    with pytest.raises(ValueError, match="feather"):
        mod.load_manifest(path)


# --- SVG sanitising -----------------------------------------------------------------------------


def test_sanitize_svg_strips_comments_and_root_size_and_adds_current_color(mod):
    raw = b'<svg xmlns="x" width="256" height="256" viewBox="0 0 256 256"><!-- c --><path d="M0 0"/></svg>'

    svg = mod.sanitize_svg(raw, label="folder")

    assert "<!--" not in svg
    assert 'width="256"' not in svg
    assert 'fill="currentColor"' in svg
    assert 'viewBox="0 0 256 256"' in svg


def test_sanitize_svg_keeps_stroke_icons_untouched(mod):
    svg = mod.sanitize_svg(MOUNTAIN_SVG.encode(), label="mountain")

    assert 'stroke="currentColor"' in svg
    assert svg.count("currentColor") == 1


def test_sanitize_svg_rejects_non_svg(mod):
    with pytest.raises(ValueError, match="not an SVG"):
        mod.sanitize_svg(b"<html></html>", label="folder")


def test_sanitize_svg_rejects_icons_that_cannot_be_tinted(mod):
    with pytest.raises(ValueError, match="currentColor"):
        mod.sanitize_svg(b'<svg viewBox="0 0 1 1" fill="#000000"><path d="M0 0"/></svg>', label="folder")


# --- download + cache ---------------------------------------------------------------------------


def make_source(mod, data: bytes = PHOSPHOR_TAR):
    return mod.Source(
        name="phosphor", package="@phosphor-icons/core", title="Phosphor Icons", version="2.1.1",
        integrity=integrity_of(data), license="MIT",
    )


def test_tarball_url_handles_scoped_packages(mod):
    assert mod.tarball_url(make_source(mod)) == "https://registry.npmjs.org/@phosphor-icons/core/-/core-2.1.1.tgz"


def test_fetch_tarball_downloads_verifies_and_caches(mod, tmp_path):
    calls = []

    def opener(url, timeout):
        calls.append(url)
        return io.BytesIO(PHOSPHOR_TAR)

    source = make_source(mod)

    first = mod.fetch_tarball(source, tmp_path, opener=opener)
    second = mod.fetch_tarball(source, tmp_path, opener=opener)

    assert first == second == PHOSPHOR_TAR
    assert len(calls) == 1


def test_fetch_tarball_rejects_tampered_download(mod, tmp_path):
    source = make_source(mod)

    with pytest.raises(ValueError, match="Integrity mismatch"):
        mod.fetch_tarball(source, tmp_path, opener=lambda url, timeout: io.BytesIO(b"tampered"))

    assert list(tmp_path.iterdir()) == []


def test_fetch_tarball_refetches_when_cache_is_corrupt(mod, tmp_path):
    source = make_source(mod)
    mod.fetch_tarball(source, tmp_path, opener=lambda url, timeout: io.BytesIO(PHOSPHOR_TAR))
    (next(tmp_path.iterdir())).write_bytes(b"corrupt")
    calls = []

    def opener(url, timeout):
        calls.append(url)
        return io.BytesIO(PHOSPHOR_TAR)

    assert mod.fetch_tarball(source, tmp_path, opener=opener) == PHOSPHOR_TAR
    assert len(calls) == 1


# --- bundle -------------------------------------------------------------------------------------


def test_build_bundle_collects_every_weight_and_the_licence(mod, tmp_path):
    manifest = mod.load_manifest(write_manifest(tmp_path, weights='["regular", "bold"]'))

    bundle = mod.build_bundle(manifest, fake_fetch)

    folder = bundle.data["icons"]["folder"]
    assert folder["source"] == "phosphor"
    assert set(folder["weights"]) == {"regular", "bold"}
    assert "<!--" not in folder["weights"]["regular"]
    assert bundle.data["sources"]["phosphor"] == {
        "package": "@phosphor-icons/core", "title": "Phosphor Icons", "version": "2.1.1", "license": "MIT",
    }
    assert bundle.licenses["phosphor"] == PHOSPHOR_LICENSE
    assert "lucide" not in bundle.data["sources"]


def test_build_bundle_applies_override_from_second_source(mod, tmp_path):
    path = write_manifest(tmp_path, icons='["folder", "mountains"]', overrides='mountains = "lucide:mountain"')
    manifest = mod.load_manifest(path)

    bundle = mod.build_bundle(manifest, fake_fetch)

    assert bundle.data["icons"]["mountains"]["source"] == "lucide"
    assert 'stroke="currentColor"' in bundle.data["icons"]["mountains"]["weights"]["regular"]
    assert bundle.data["icons"]["folder"]["source"] == "phosphor"
    assert set(bundle.data["sources"]) == {"phosphor", "lucide"}
    assert bundle.licenses["lucide"] == LUCIDE_LICENSE


def test_build_bundle_reports_all_missing_icons_at_once(mod, tmp_path):
    manifest = mod.load_manifest(write_manifest(tmp_path, icons='["folder", "nope", "also-nope"]'))

    with pytest.raises(ValueError) as error:
        mod.build_bundle(manifest, fake_fetch)

    assert "nope" in str(error.value) and "also-nope" in str(error.value)


def test_build_bundle_normalises_licence_line_endings(mod, tmp_path):
    crlf_tar = make_tarball({"LICENSE": "MIT License\r\nCopyright (c) 2023 X\r\n", "assets/regular/folder.svg": FOLDER_SVG})
    manifest = mod.load_manifest(write_manifest(tmp_path))

    bundle = mod.build_bundle(manifest, lambda source: crlf_tar)

    assert "\r" not in bundle.licenses["phosphor"]


def test_render_notices_lists_copyright_and_icons_per_source(mod, tmp_path):
    path = write_manifest(tmp_path, icons='["folder", "mountains"]', overrides='mountains = "lucide:mountain"')
    bundle = mod.build_bundle(mod.load_manifest(path), fake_fetch)

    notices = mod.render_notices(bundle.data, bundle.licenses)

    assert "Phosphor Icons 2.1.1" in notices
    assert "Copyright (c) 2023 Phosphor Icons" in notices
    assert "Copyright (c) 2026 Lucide Icons and Contributors" in notices
    assert "folder" in notices and "mountains" in notices
    assert "licenses/phosphor-LICENSE.txt" in notices


def test_dump_bundle_is_deterministic_json(mod, tmp_path):
    bundle = mod.build_bundle(mod.load_manifest(write_manifest(tmp_path)), fake_fetch)

    text = mod.dump_bundle(bundle.data)

    assert text == mod.dump_bundle(json.loads(text))
    assert text.endswith("\n")


# --- run / --check ------------------------------------------------------------------------------


def test_run_writes_outputs_and_check_detects_drift(mod, tmp_path):
    manifest_path = write_manifest(tmp_path)
    icons_dir = tmp_path / "icons"
    notices = tmp_path / "NOTICES.md"
    kwargs = {"icons_dir": icons_dir, "notices_path": notices, "fetch": fake_fetch}

    assert mod.run(manifest_path, check=False, **kwargs) == 0
    assert (icons_dir / "icon_bundle.json").is_file()
    assert (icons_dir / "licenses" / "phosphor-LICENSE.txt").read_text(encoding="utf-8") == PHOSPHOR_LICENSE
    assert notices.is_file()
    assert mod.run(manifest_path, check=True, **kwargs) == 0

    (icons_dir / "icon_bundle.json").write_text("{}", encoding="utf-8")
    assert mod.run(manifest_path, check=True, **kwargs) == 1


def test_run_removes_licence_files_of_sources_no_longer_used(mod, tmp_path):
    manifest_path = write_manifest(tmp_path)
    icons_dir = tmp_path / "icons"
    (icons_dir / "licenses").mkdir(parents=True)
    stale = icons_dir / "licenses" / "lucide-LICENSE.txt"
    stale.write_text("old", encoding="utf-8")
    kwargs = {"icons_dir": icons_dir, "notices_path": tmp_path / "N.md", "fetch": fake_fetch}

    assert mod.run(manifest_path, check=True, **kwargs) == 1
    assert mod.run(manifest_path, check=False, **kwargs) == 0

    assert not stale.exists()
