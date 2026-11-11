"""Building the icon bundle data from the manifest and the upstream packages."""

import json
from collections.abc import Callable
from dataclasses import dataclass

from icon_bundle.fetch import read_package_files
from icon_bundle.layouts import DEFAULT_SOURCE, upstream_path
from icon_bundle.manifest import Manifest, Source
from icon_bundle.svg import sanitize_svg

SCHEMA_VERSION = 1


@dataclass
class Bundle:
    """Generated bundle content: the JSON-serialisable data and the licence text per used source."""

    data: dict
    licenses: dict[str, str]


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
        paths = {weight: upstream_path(source, upstream_name, weight) for weight in manifest.weights}
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
