"""Command-line entry point: generate or verify the bundle, licence files and notices."""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from icon_bundle.bundle import build_bundle, dump_bundle
from icon_bundle.fetch import fetch_tarball
from icon_bundle.manifest import Source, load_manifest
from icon_bundle.notices import render_notices

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ICONS_DIR = REPO_ROOT / "pandaplot" / "gui" / "resources" / "icons"
MANIFEST_PATH = ICONS_DIR / "icon_manifest.toml"
NOTICES_PATH = REPO_ROOT / "THIRD_PARTY_NOTICES.md"
DEFAULT_CACHE_DIR = REPO_ROOT / ".icon-cache"
BUNDLE_NAME = "icon_bundle.json"


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
    parser = argparse.ArgumentParser(description="Build the checked-in icon bundle from upstream npm icon packages.")
    parser.add_argument("--check", action="store_true", help="exit 1 if the committed files are out of date instead of writing")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="where downloaded tarballs are cached")
    args = parser.parse_args(argv)

    def fetch(source: Source) -> bytes:
        return fetch_tarball(source, args.cache_dir)

    return run(MANIFEST_PATH, icons_dir=ICONS_DIR, notices_path=NOTICES_PATH, fetch=fetch, check=args.check)
