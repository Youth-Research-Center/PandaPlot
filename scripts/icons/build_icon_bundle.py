#!/usr/bin/env python3
"""Build the checked-in icon bundle from upstream npm icon packages.

Edit ``pandaplot/gui/resources/icons/icon_manifest.toml`` (add an icon name to ``icons``), then run:

    uv run python scripts/icons/build_icon_bundle.py            # regenerate bundle, licences and notices
    uv run python scripts/icons/build_icon_bundle.py --check    # exit 1 when the committed files are out of date

Upstream packages are pinned by version and sha512 integrity in the manifest, downloaded once into
``.icon-cache/`` (git-ignored) and read in memory: nothing from the archive is ever extracted to disk.
The application never downloads icons; it only reads the committed ``icon_bundle.json``.
"""

import argparse
import base64
import hashlib
import io
import json
import re
import sys
import tarfile
import tomllib
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ICONS_DIR = REPO_ROOT / "pandaplot" / "gui" / "resources" / "icons"
MANIFEST_PATH = ICONS_DIR / "icon_manifest.toml"
NOTICES_PATH = REPO_ROOT / "THIRD_PARTY_NOTICES.md"
DEFAULT_CACHE_DIR = REPO_ROOT / ".icon-cache"
BUNDLE_NAME = "icon_bundle.json"
SCHEMA_VERSION = 1
DEFAULT_SOURCE = "phosphor"
KNOWN_WEIGHTS = ("thin", "light", "regular", "bold", "fill", "duotone")

_ICON_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_ROOT_TAG = re.compile(r"<svg\b[^>]*>")
_ROOT_SIZE = re.compile(r'\s(?:width|height)="[^"]*"')
_COPYRIGHT = re.compile(r"^Copyright.*$", re.MULTILINE)


def _phosphor_path(name: str, weight: str) -> str:
    suffix = "" if weight == "regular" else f"-{weight}"
    return f"assets/{weight}/{name}{suffix}.svg"


# Lucide has a single weight, so the weight argument is ignored.
def _lucide_path(name: str, weight: str) -> str:
    return f"icons/{name}.svg"


# Where each supported library keeps its SVGs inside its npm package. Adding a library means adding a layout here.
_LAYOUTS: dict[str, Callable[[str, str], str]] = {"phosphor": _phosphor_path, "lucide": _lucide_path}


@dataclass
class Source:
    """A pinned upstream npm package that icons are taken from."""

    name: str
    package: str
    title: str
    version: str
    integrity: str
    license: str


@dataclass
class Manifest:
    """Parsed ``icon_manifest.toml``."""

    weights: tuple[str, ...]
    sources: dict[str, Source]
    icons: tuple[str, ...]
    overrides: dict[str, tuple[str, str]]


@dataclass
class Bundle:
    """Generated bundle content: the JSON-serialisable data and the licence text per used source."""

    data: dict
    licenses: dict[str, str]


def load_manifest(path: Path) -> Manifest:
    """Parse and validate the icon manifest.

    Args:
        path: Path to ``icon_manifest.toml``.

    Returns:
        The validated manifest.

    Raises:
        ValueError: If a weight, source, icon name or override is invalid.
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    weights = tuple(data.get("weights", ["regular"]))
    unknown = [weight for weight in weights if weight not in KNOWN_WEIGHTS]
    if unknown:
        raise ValueError(f"Unknown weight(s) {unknown}; expected a subset of {list(KNOWN_WEIGHTS)}")

    sources: dict[str, Source] = {}
    for name, config in data.get("sources", {}).items():
        if name not in _LAYOUTS:
            raise ValueError(f"No file layout is known for source '{name}'")
        sources[name] = Source(
            name=name, package=config["package"], title=config["title"], version=config["version"],
            integrity=config["integrity"], license=config["license"],
        )
    if DEFAULT_SOURCE not in sources:
        raise ValueError(f"The default source '{DEFAULT_SOURCE}' must be declared under [sources]")

    icons = tuple(data.get("icons", []))
    if len(set(icons)) != len(icons):
        raise ValueError("Duplicate icon names in 'icons'")
    for icon in icons:
        if not _ICON_NAME.match(icon):
            raise ValueError(f"Invalid icon name '{icon}': use lowercase letters, digits and hyphens")

    overrides: dict[str, tuple[str, str]] = {}
    for icon, reference in data.get("overrides", {}).items():
        source, _, upstream_name = reference.partition(":")
        if source not in sources or not upstream_name:
            raise ValueError(f"Override '{icon}' = '{reference}' must look like 'source:name' with a declared source ('{source}')")
        if icon not in icons:
            raise ValueError(f"Override '{icon}' is not listed in 'icons'")
        overrides[icon] = (source, upstream_name)

    return Manifest(weights=weights, sources=sources, icons=icons, overrides=overrides)


def sanitize_svg(raw: bytes, *, label: str) -> str:
    """Normalise an upstream SVG so it can be tinted and embedded.

    Strips comments and the root ``width``/``height``, and adds ``fill="currentColor"`` when the root
    sets neither ``fill`` nor ``stroke``.

    Raises:
        ValueError: If the document is not an SVG or contains no ``currentColor`` (it could not be tinted).
    """
    text = _COMMENT.sub("", raw.decode("utf-8")).strip()
    match = _ROOT_TAG.match(text)
    if match is None:
        raise ValueError(f"{label} is not an SVG document")
    root = _ROOT_SIZE.sub("", match.group(0))
    if "fill=" not in root and "stroke=" not in root:
        root = root.replace("<svg", '<svg fill="currentColor"', 1)
    svg = root + text[match.end():]
    if "currentColor" not in svg:
        raise ValueError(f"{label} has no currentColor, so it cannot be tinted by the theme")
    return svg


def tarball_url(source: Source) -> str:
    """Return the npm registry URL of the source's pinned tarball."""
    basename = source.package.rsplit("/", 1)[-1]
    return f"https://registry.npmjs.org/{source.package}/-/{basename}-{source.version}.tgz"


def verify_integrity(data: bytes, integrity: str, *, label: str) -> None:
    """Raise ``ValueError`` unless ``data`` matches an npm ``sha512-<base64>`` integrity string."""
    algorithm, _, expected = integrity.partition("-")
    if algorithm != "sha512":
        raise ValueError(f"Unsupported integrity algorithm for {label}: '{algorithm}'")
    actual = base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")
    if actual != expected:
        raise ValueError(f"Integrity mismatch for {label}: expected {expected}, got {actual}")


def fetch_tarball(source: Source, cache_dir: Path, *, opener: Callable = urllib.request.urlopen) -> bytes:
    """Return the source's tarball bytes, from the verified local cache or the npm registry.

    Args:
        source: The pinned package.
        cache_dir: Directory that caches verified tarballs.
        opener: Callable with the ``urllib.request.urlopen(url, timeout=...)`` shape (injectable for tests).

    Raises:
        ValueError: If the downloaded bytes do not match the pinned integrity. Nothing is cached in that case.
    """
    label = f"{source.package}@{source.version}"
    cache_path = cache_dir / f"{source.package.replace('/', '__')}-{source.version}.tgz"
    if cache_path.is_file():
        cached = cache_path.read_bytes()
        try:
            verify_integrity(cached, source.integrity, label=label)
        except ValueError as error:
            print(f"Ignoring corrupt cache entry {cache_path}: {error}", file=sys.stderr)
        else:
            return cached
    with opener(tarball_url(source), timeout=60) as response:
        data = response.read()
    verify_integrity(data, source.integrity, label=label)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(data)
    return data


def read_package_files(tarball: bytes, wanted: set[str]) -> dict[str, bytes]:
    """Read the wanted ``package/<path>`` files from an npm tarball in memory (nothing is extracted to disk)."""
    found: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as archive:
        for member in archive:
            relative = member.name.removeprefix("package/")
            if relative in wanted and member.isfile():
                handle = archive.extractfile(member)
                if handle is not None:
                    found[relative] = handle.read()
    return found


def build_bundle(manifest: Manifest, fetch: Callable[[Source], bytes]) -> Bundle:
    """Build the bundle data and licence texts described by the manifest.

    Args:
        manifest: The parsed manifest.
        fetch: Returns the tarball bytes for a source.

    Raises:
        ValueError: Listing every icon file missing from the upstream packages.
    """
    plan: dict[str, dict[str, dict[str, str]]] = {}  # source -> icon -> weight -> upstream path
    for icon in manifest.icons:
        source, upstream_name = manifest.overrides.get(icon, (DEFAULT_SOURCE, icon))
        paths = {weight: _LAYOUTS[source](upstream_name, weight) for weight in manifest.weights}
        plan.setdefault(source, {})[icon] = paths

    data: dict = {"schema_version": SCHEMA_VERSION, "sources": {}, "icons": {}}
    licenses: dict[str, str] = {}
    missing: list[str] = []
    for source_name, icons in sorted(plan.items()):
        source = manifest.sources[source_name]
        wanted = {path for paths in icons.values() for path in paths.values()} | {"LICENSE"}
        files = read_package_files(fetch(source), wanted)
        if "LICENSE" not in files:
            raise ValueError(f"{source.package} has no LICENSE file")
        licenses[source_name] = files["LICENSE"].decode("utf-8").replace("\r\n", "\n")
        data["sources"][source_name] = {
            "package": source.package, "title": source.title, "version": source.version, "license": source.license,
        }
        for icon, paths in icons.items():
            weights: dict[str, str] = {}
            for weight, path in paths.items():
                if path not in files:
                    missing.append(f"{icon} ({source_name}: {path})")
                    continue
                weights[weight] = sanitize_svg(files[path], label=f"{source_name}:{path}")
            data["icons"][icon] = {"source": source_name, "weights": weights}
    if missing:
        raise ValueError("Icons missing from upstream packages: " + ", ".join(missing))
    return Bundle(data=data, licenses=licenses)


def dump_bundle(data: dict) -> str:
    """Serialise the bundle deterministically (sorted keys, one level of indentation)."""
    return json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def render_notices(data: dict, licenses: dict[str, str]) -> str:
    """Render ``THIRD_PARTY_NOTICES.md`` for the sources used by the bundle."""
    lines = [
        "# Third-party notices",
        "",
        "<!-- Generated by scripts/icons/build_icon_bundle.py. Do not edit by hand. -->",
        "",
        "PandaPlot bundles icons from the open-source libraries below. Each library's full licence text ships with the",
        "application in `pandaplot/gui/resources/icons/licenses/`.",
        "",
    ]
    for name, meta in sorted(data["sources"].items()):
        match = _COPYRIGHT.search(licenses[name])
        copyright_line = match.group(0).strip() if match else "see the licence text"
        used = sorted(icon for icon, entry in data["icons"].items() if entry["source"] == name)
        lines += [
            f"## {meta['title']} {meta['version']}",
            "",
            f"- Package: `{meta['package']}`",
            f"- Licence: {meta['license']}",
            f"- {copyright_line}",
            f"- Icons used: {', '.join(used)}",
            f"- Full licence text: `pandaplot/gui/resources/icons/licenses/{name}-LICENSE.txt`",
            "",
        ]
    return "\n".join(lines)


def run(manifest_path: Path, *, icons_dir: Path, notices_path: Path, fetch: Callable[[Source], bytes], check: bool) -> int:
    """Generate (or verify) the bundle, licence files and notices.

    Returns:
        Process exit code: 0 on success, 1 when ``check`` finds out-of-date files.
    """
    bundle = build_bundle(load_manifest(manifest_path), fetch)
    licenses_dir = icons_dir / "licenses"
    outputs: dict[Path, str] = {
        icons_dir / BUNDLE_NAME: dump_bundle(bundle.data),
        notices_path: render_notices(bundle.data, bundle.licenses),
    }
    for source, text in bundle.licenses.items():
        outputs[licenses_dir / f"{source}-LICENSE.txt"] = text
    stale = sorted(path for path in licenses_dir.glob("*-LICENSE.txt") if path not in outputs) if licenses_dir.is_dir() else []

    if check:
        drifted = [path for path, text in outputs.items() if not path.is_file() or path.read_text(encoding="utf-8") != text]
        drifted += stale
        for path in drifted:
            print(f"Out of date: {path}", file=sys.stderr)
        return 1 if drifted else 0

    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    for path in stale:
        path.unlink()
    print(f"Wrote {len(bundle.data['icons'])} icons from {len(bundle.data['sources'])} source(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the committed files are out of date instead of writing")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="where downloaded tarballs are cached")
    args = parser.parse_args(argv)

    def fetch(source: Source) -> bytes:
        return fetch_tarball(source, args.cache_dir)

    return run(MANIFEST_PATH, icons_dir=ICONS_DIR, notices_path=NOTICES_PATH, fetch=fetch, check=args.check)


if __name__ == "__main__":
    sys.exit(main())
