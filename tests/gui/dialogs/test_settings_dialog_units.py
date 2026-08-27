"""Tests for the Settings dialog's measurement-unit control (General tab)."""
import sys

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.dialogs.settings_dialog import SettingsDialog
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.state.config import LengthUnit
from pandaplot.services.config.config_manager import ConfigManager


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _isolated_dialog(tmp_path):
    """Build a SettingsDialog backed by a throwaway ConfigManager (a tmp_path
    config file) instead of the real ~/.pandaplot/config.json, so tests never
    touch the developer's actual settings."""
    _qapp()
    app_context = build_app_context()
    dialog = SettingsDialog(app_context)
    dialog._config_manager = ConfigManager(EventBus(), config_path=tmp_path / "config.json")
    dialog._config_manager.load()
    dialog.load_current_settings()
    return dialog


def test_default_unit_is_cm_with_cm_suffix_and_values(tmp_path):
    dialog = _isolated_dialog(tmp_path)
    assert dialog._chart_size_unit == LengthUnit.CM
    assert dialog.chart_width_spin.suffix() == " cm"
    assert dialog.chart_width_spin.value() == 20.0
    assert dialog.chart_height_spin.value() == 15.0


def test_switching_to_mm_converts_displayed_values(tmp_path):
    dialog = _isolated_dialog(tmp_path)
    dialog.chart_unit_combo.setCurrentText("Millimeters (mm)")
    assert dialog._chart_size_unit == LengthUnit.MM
    assert dialog.chart_width_spin.suffix() == " mm"
    assert dialog.chart_width_spin.decimals() == 0
    assert dialog.chart_width_spin.value() == 200
    assert dialog.chart_height_spin.value() == 150


def test_get_current_settings_from_ui_returns_centimeters_regardless_of_unit(tmp_path):
    dialog = _isolated_dialog(tmp_path)
    dialog.chart_unit_combo.setCurrentText("Millimeters (mm)")
    settings = dialog.get_current_settings_from_ui()
    assert settings["chart_width"] == 20.0
    assert settings["chart_height"] == 15.0
    assert settings["measurement_unit"] == "mm"


def test_apply_settings_persists_measurement_unit(tmp_path):
    dialog = _isolated_dialog(tmp_path)
    dialog.chart_unit_combo.setCurrentText("Inches (in)")
    dialog.apply_settings()
    assert dialog._config_manager.config.chart_display.measurement_unit == LengthUnit.IN


def test_reopening_with_no_changes_does_not_look_dirty(tmp_path):
    """Regression guard: converting cm defaults to a lossy unit like inches
    for display must not make get_current_settings_from_ui() disagree with
    original_settings just from unit round-trip rounding (reject() compares
    these dicts to decide whether to warn about unsaved changes)."""
    dialog = _isolated_dialog(tmp_path)
    dialog._config_manager.update({"chart_display": {"measurement_unit": "in"}}, save=True)
    dialog.load_current_settings()
    assert dialog.get_current_settings_from_ui() == dialog.original_settings


def test_apply_settings_preserves_exact_cm_when_size_unchanged_under_lossy_unit(tmp_path):
    """Regression guard: switching to a lossy display unit (inches) and
    applying without touching width/height must not silently rewrite the
    stored centimeter defaults to a rounded approximation (20cm displays as
    7.87in, which converts back to 19.9898cm, not 20.0)."""
    dialog = _isolated_dialog(tmp_path)
    dialog.chart_unit_combo.setCurrentText("Inches (in)")
    dialog.apply_settings()
    assert dialog._config_manager.config.chart_display.default_width_cm == 20.0
    assert dialog._config_manager.config.chart_display.default_height_cm == 15.0


def test_apply_settings_persists_actual_size_change_under_lossy_unit(tmp_path):
    """A genuine edit to the width spin box must still be saved, even though
    the "did the user change this" check is itself unit-quantized."""
    dialog = _isolated_dialog(tmp_path)
    dialog.chart_unit_combo.setCurrentText("Inches (in)")
    dialog.chart_width_spin.setValue(10.0)  # a real edit, in inches
    dialog.apply_settings()
    assert dialog._config_manager.config.chart_display.default_width_cm == pytest.approx(10.0 * 2.54)
