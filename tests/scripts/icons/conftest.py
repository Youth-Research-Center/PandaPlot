"""Shared helpers for the icon bundle tests (offline: upstream tarballs are built in memory)."""

import base64
import hashlib
import io
import tarfile
from pathlib import Path

from icon_bundle.manifest import Source

PHOSPHOR_LICENSE = "MIT License\n\nCopyright (c) 2023 Phosphor Icons\n\nPermission is hereby granted...\n"
LUCIDE_LICENSE = "ISC License\n\nCopyright (c) 2026 Lucide Icons and Contributors\n"
FOLDER_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><!-- c --><path d="M0 0h8v8z"/></svg>'
MOUNTAIN_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor"><path d="m8 3 4 8"/></svg>'
)


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


def fake_fetch(source: Source) -> bytes:
    return {"phosphor": PHOSPHOR_TAR, "lucide": LUCIDE_TAR}[source.name]


def make_source(data: bytes = PHOSPHOR_TAR) -> Source:
    return Source(
        name="phosphor", package="@phosphor-icons/core", title="Phosphor Icons", version="2.1.1",
        integrity=integrity_of(data), license="MIT",
    )
