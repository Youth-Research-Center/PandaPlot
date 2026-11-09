"""Parsing and validation of ``icon_manifest.toml``."""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from icon_bundle.layouts import DEFAULT_SOURCE, KNOWN_WEIGHTS, LAYOUTS

_ICON_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


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
        if name not in LAYOUTS:
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
