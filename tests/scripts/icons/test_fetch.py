"""Tests for icon_bundle.fetch (download + cache)."""

import io

import pytest
from icon_bundle.fetch import fetch_tarball, tarball_url

from tests.scripts.icons.conftest import PHOSPHOR_TAR, make_source


def test_tarball_url_handles_scoped_packages():
    assert tarball_url(make_source()) == "https://registry.npmjs.org/@phosphor-icons/core/-/core-2.1.1.tgz"


def test_fetch_tarball_downloads_verifies_and_caches(tmp_path):
    calls = []

    def opener(url, timeout):
        calls.append(url)
        return io.BytesIO(PHOSPHOR_TAR)

    source = make_source()

    first = fetch_tarball(source, tmp_path, opener=opener)
    second = fetch_tarball(source, tmp_path, opener=opener)

    assert first == second == PHOSPHOR_TAR
    assert len(calls) == 1


def test_fetch_tarball_rejects_tampered_download(tmp_path):
    source = make_source()

    with pytest.raises(ValueError, match="Integrity mismatch"):
        fetch_tarball(source, tmp_path, opener=lambda url, timeout: io.BytesIO(b"tampered"))

    assert list(tmp_path.iterdir()) == []


def test_fetch_tarball_refetches_when_cache_is_corrupt(tmp_path):
    source = make_source()
    fetch_tarball(source, tmp_path, opener=lambda url, timeout: io.BytesIO(PHOSPHOR_TAR))
    (next(tmp_path.iterdir())).write_bytes(b"corrupt")
    calls = []

    def opener(url, timeout):
        calls.append(url)
        return io.BytesIO(PHOSPHOR_TAR)

    assert fetch_tarball(source, tmp_path, opener=opener) == PHOSPHOR_TAR
    assert len(calls) == 1
