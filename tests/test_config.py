"""Unit tests for the configuration data model (Phase 1.1).

These tests focus purely on the data model behavior implemented in
`pandaplot.models.state.config`:
    * Defaults & serialization
    * Update / partial merges & coercion
    * Validation fallbacks (interval, tab size, font sizes)
    * Enum parsing (Theme)
    * Reset & cloning
    * Robustness against malformed / unknown input
"""
from __future__ import annotations

import pytest

from pandaplot.models.state.config import (
    ApplicationConfig,
    Theme,
)


def test_defaults_and_serialization_roundtrip():
    cfg = ApplicationConfig.default()
    d = cfg.to_dict()
    assert d["version"] == cfg.version
    assert d["appearance"]["theme"] in {t.value for t in Theme}
    # roundtrip via json
    json_text = cfg.to_json()
    loaded = ApplicationConfig.from_json(json_text)
    assert loaded.appearance.theme == cfg.appearance.theme
    assert loaded.editor.tab_size == 4


def test_update_basic_and_coercion():
    cfg = ApplicationConfig.default()
    cfg.update_from_mapping(
        {
            "auto_save": {"interval_seconds": -5, "enabled": False},  # invalid -> fallback 60
            "appearance": {"theme": "dark", "accent_color": "#FF0000"},
            "editor": {"word_wrap": "off", "tab_size": 100},  # wrap str -> False, tab capped to 16
        }
    )
    assert cfg.auto_save.enabled is False
    assert cfg.auto_save.interval_seconds == 60  # validated fallback
    assert cfg.appearance.theme == Theme.DARK
    assert cfg.appearance.accent_color == "#FF0000"
    assert cfg.editor.word_wrap is False
    assert cfg.editor.tab_size == 16  # upper bound applied


def test_update_bool_string_variants():
    cfg = ApplicationConfig.default()
    cfg.update_from_mapping({"editor": {"line_numbers": "NO"}})
    assert cfg.editor.line_numbers is False
    cfg.update_from_mapping({"editor": {"line_numbers": "yes"}})
    assert cfg.editor.line_numbers is True


def test_enum_name_and_value_parsing():
    cfg = ApplicationConfig.default()
    cfg.update_from_mapping({"appearance": {"theme": "light"}})  # by value
    assert cfg.appearance.theme == Theme.LIGHT
    cfg.update_from_mapping({"appearance": {"theme": "DARK"}})  # by name (case-insensitive via upper)
    assert cfg.appearance.theme == Theme.DARK


def test_invalid_enum_value_is_ignored():
    cfg = ApplicationConfig.default()
    original = cfg.appearance.theme
    cfg.update_from_mapping({"appearance": {"theme": "totally-unknown"}})
    assert cfg.appearance.theme == original  # unchanged


def test_unknown_sections_and_keys_are_ignored():
    cfg = ApplicationConfig.default()
    cfg.update_from_mapping(
        {
            "nonexistent": {"foo": 1},
            "appearance": {"non_key": 123, "theme": "system"},
        }
    )
    # Ensure nothing exploded and theme accepted
    assert cfg.appearance.theme == Theme.SYSTEM
    # Ensure no accidental attribute created
    assert not hasattr(cfg.appearance, "non_key")


def test_from_json_with_malformed_input_returns_default():
    malformed = "{ this is not valid json"  # missing closing brace
    cfg = ApplicationConfig.from_json(malformed)
    assert isinstance(cfg, ApplicationConfig)
    assert cfg.editor.tab_size == 4


def test_reset_defaults_restores_values():
    cfg = ApplicationConfig.default()
    cfg.update_from_mapping({"editor": {"tab_size": 8}, "appearance": {"theme": "dark"}})
    assert cfg.editor.tab_size == 8
    assert cfg.appearance.theme == Theme.DARK
    cfg.reset_defaults()
    assert cfg.editor.tab_size == 4
    assert cfg.appearance.theme == Theme.SYSTEM


def test_clone_is_deep_copy():
    cfg = ApplicationConfig.default()
    cloned = cfg.clone()
    assert cloned.to_dict() == cfg.to_dict()
    # mutate clone and ensure original not affected
    cloned.editor.tab_size = 2
    assert cfg.editor.tab_size == 4


@pytest.mark.parametrize(
    "input_value,expected",
    [
        ("true", True),
        ("False", False),
        ("ON", True),
        ("off", False),
        ("YES", True),
        ("no", False),
    ],
)
def test_bool_string_matrix(input_value: str, expected: bool):
    cfg = ApplicationConfig.default()
    cfg.update_from_mapping({"auto_save": {"enabled": input_value}})
    assert cfg.auto_save.enabled is expected


def test_font_size_validation_lower_bound():
    cfg = ApplicationConfig.default()
    cfg.update_from_mapping({"appearance": {"interface_font_size": 4, "editor_font_size": 5}})
    # Since invalid small ints get coerced -> validate ensures >=8 ( but update only sets ints )
    assert cfg.appearance.interface_font_size == 8
    assert cfg.appearance.editor_font_size == 8
