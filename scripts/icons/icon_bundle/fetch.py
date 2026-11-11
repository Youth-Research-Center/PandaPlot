"""Downloading, verifying, caching and reading the pinned upstream npm tarballs."""

import base64
import hashlib
import io
import sys
import tarfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

from icon_bundle.manifest import Source


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
