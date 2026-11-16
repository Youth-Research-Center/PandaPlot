"""WCAG helpers shared by the design tokens and ThemeManager."""

import pytest
from PySide6.QtGui import QColor

from pandaplot.services.theme.contrast import adjust_until_contrast, contrast_ratio, contrasting_text_color, mix, relative_luminance


def test_relative_luminance_of_black_and_white() -> None:
    assert relative_luminance(QColor("#000000")) == 0.0
    assert relative_luminance(QColor("#FFFFFF")) == pytest.approx(1.0)


def test_contrast_ratio_matches_wcag_reference_values() -> None:
    assert contrast_ratio(QColor("#000000"), QColor("#FFFFFF")) == pytest.approx(21.0)
    assert contrast_ratio(QColor("#FFFFFF"), QColor("#0E7C86")) == pytest.approx(4.95, abs=0.01)
    assert contrast_ratio(QColor("#0E7C86"), QColor("#FFFFFF")) == contrast_ratio(QColor("#FFFFFF"), QColor("#0E7C86"))


@pytest.mark.parametrize(("background", "expected"), [("#0E7C86", "#ffffff"), ("#F07171", "#000000"), ("#4A56C6", "#ffffff")])
def test_contrasting_text_color_picks_the_more_legible_of_black_and_white(background: str, expected: str) -> None:
    assert contrasting_text_color(QColor(background)).name() == expected


def test_adjust_until_contrast_returns_start_when_it_already_passes() -> None:
    assert adjust_until_contrast(QColor("#0A5F67"), QColor("#E3F4F5"), min_ratio=4.5, lighten=False).name() == "#0a5f67"


@pytest.mark.parametrize("lighten", [True, False])
def test_adjust_until_contrast_steps_until_the_ratio_is_met(*, lighten: bool) -> None:
    background = QColor("#2E3350") if lighten else QColor("#EEF0FB")
    result = adjust_until_contrast(QColor("#4A56C6"), background, min_ratio=4.5, lighten=lighten)

    assert contrast_ratio(result, background) >= 4.5


def test_adjust_until_contrast_falls_back_to_black_or_white() -> None:
    background = QColor("#808080")
    result = adjust_until_contrast(QColor("#7F7F7F"), background, min_ratio=21.0, lighten=True)

    assert result.name() == contrasting_text_color(background).name()


def test_mix_interpolates_each_channel() -> None:
    assert mix("#000000", "#FFFFFF", 0.0) == "#000000"
    assert mix("#000000", "#FFFFFF", 1.0) == "#FFFFFF"
    assert mix("#0E7C86", "#FFFFFF", 0.55) == "#93C4C9"
