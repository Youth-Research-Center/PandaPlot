#!/usr/bin/env python3
"""Build the checked-in icon bundle from upstream npm icon packages.

Edit ``pandaplot/gui/resources/icons/icon_manifest.toml`` (add an icon name to ``icons``), then run:

    uv run python scripts/icons/build_icon_bundle.py            # regenerate bundle, licences and notices
    uv run python scripts/icons/build_icon_bundle.py --check    # exit 1 when the committed files are out of date

Upstream packages are pinned by version and sha512 integrity in the manifest, downloaded once into
``.icon-cache/`` (git-ignored) and read in memory: nothing from the archive is ever extracted to disk.
The application never downloads icons; it only reads the committed ``icon_bundle.json``.

The implementation lives in the ``icon_bundle`` package next to this file.
"""

import sys
from pathlib import Path

# ``python -I`` does not put the script directory on sys.path, so add it explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from icon_bundle.cli import main

if __name__ == "__main__":
    sys.exit(main())
