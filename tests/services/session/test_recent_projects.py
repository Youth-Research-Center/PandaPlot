"""Tests for the shared get_recent_projects lookup.

Extracted from WelcomeTab (see #221) so MainMenu's File > Recent submenu can
reuse the exact same filtering/sorting rules.
"""
import os
import time
from unittest.mock import Mock

from pandaplot.services.config.config_manager import ConfigManager
from pandaplot.services.session.recent_projects import get_recent_projects


def _app_context_with_recent(paths):
    cfg = Mock()
    cfg.recent_projects = paths
    cfg_manager = Mock()
    cfg_manager.config = cfg
    ctx = Mock()
    ctx.get_manager.side_effect = lambda t: cfg_manager if t is ConfigManager else Mock()
    return ctx


def test_returns_empty_list_when_no_app_context():
    assert get_recent_projects(None) == []


def test_returns_empty_list_when_no_recent_projects_configured():
    ctx = _app_context_with_recent([])
    assert get_recent_projects(ctx) == []


def test_filters_out_paths_that_no_longer_exist(tmp_path):
    existing = tmp_path / "project_a.pplot"
    existing.write_text("{}")
    missing = str(tmp_path / "does_not_exist.pplot")

    ctx = _app_context_with_recent([str(existing), missing])

    results = get_recent_projects(ctx)

    assert [r["path"] for r in results] == [str(existing)]


def test_derives_name_from_file_stem(tmp_path):
    project_file = tmp_path / "My Project.pplot"
    project_file.write_text("{}")

    ctx = _app_context_with_recent([str(project_file)])

    results = get_recent_projects(ctx)

    assert results[0]["name"] == "My Project"


def test_sorts_newest_first_by_last_opened(tmp_path):
    older = tmp_path / "older.pplot"
    newer = tmp_path / "newer.pplot"
    older.write_text("{}")
    newer.write_text("{}")

    now = time.time()
    os.utime(older, (now - 3600, now - 3600))
    os.utime(newer, (now, now))

    ctx = _app_context_with_recent([str(older), str(newer)])

    results = get_recent_projects(ctx)

    assert [r["path"] for r in results] == [str(newer), str(older)]


def test_returns_empty_list_when_config_manager_lookup_raises():
    ctx = Mock()
    ctx.get_manager.side_effect = RuntimeError("boom")

    assert get_recent_projects(ctx) == []
