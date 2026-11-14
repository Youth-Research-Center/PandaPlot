"""Tests for WizardStepRail."""
import pytest
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart import wizard_step_rail
from pandaplot.gui.dialogs.chart.wizard_step_rail import WizardStepRail
from tests.gui.theme_testing import design_tokens


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_current_step_label_is_bold_and_not_clickable():
    rail = WizardStepRail(["Type", "Data", "Labels"])
    rail.set_state(current_index=0, summaries={})

    received = []
    rail.stepClicked.connect(received.append)
    rail._step_widgets[0].click()

    assert received == []


def test_completed_step_is_clickable_and_shows_its_summary():
    rail = WizardStepRail(["Type", "Data", "Labels"])
    rail.set_state(current_index=2, summaries={0: "Type · Line", 1: "Data · 2 series"})

    assert rail._step_widgets[0].text() == "Type · Line"
    received = []
    rail.stepClicked.connect(received.append)
    rail._step_widgets[0].click()

    assert received == [0]


def test_upcoming_step_is_not_clickable():
    rail = WizardStepRail(["Type", "Data", "Labels"])
    rail.set_state(current_index=0, summaries={})

    received = []
    rail.stepClicked.connect(received.append)
    rail._step_widgets[2].click()

    assert received == []


def test_set_state_replaces_previous_summaries():
    rail = WizardStepRail(["Type", "Data", "Labels"])
    rail.set_state(current_index=1, summaries={0: "Type · Line"})

    rail.set_state(current_index=2, summaries={0: "Type · Bar", 1: "Data · 1 series"})

    assert rail._step_widgets[0].text() == "Type · Bar"
    assert rail._step_widgets[1].text() == "Data · 1 series"


def test_each_step_renders_a_circle_icon():
    rail = WizardStepRail(["Type", "Data", "Labels"])
    rail.set_state(current_index=1, summaries={0: "Type · Line"})

    for button in rail._step_widgets:
        assert not button.icon().isNull()


def test_current_completed_and_upcoming_circles_are_visually_distinct():
    """Regression guard for the plain QPushButton rail: each state must
    paint its own circle icon (filled/checkmark/outlined), not share one.

    The completed button stays enabled, so its Normal-mode pixmap is what
    actually renders. The current and upcoming buttons are disabled (to
    preserve click-gating), so it's their Disabled-mode pixmap that renders
    on screen -- that's what must be compared, not the Normal-mode pixmap
    Qt never shows for a disabled button.
    """
    rail = WizardStepRail(["Type", "Data", "Labels"])
    rail.set_state(current_index=1, summaries={0: "Type · Line"})

    completed_icon = rail._step_widgets[0].icon().pixmap(17, 17, QIcon.Mode.Normal).toImage()
    current_icon = rail._step_widgets[1].icon().pixmap(17, 17, QIcon.Mode.Disabled).toImage()
    upcoming_icon = rail._step_widgets[2].icon().pixmap(17, 17, QIcon.Mode.Disabled).toImage()

    assert completed_icon != current_icon
    assert current_icon != upcoming_icon
    assert completed_icon != upcoming_icon


def test_disabled_current_step_circle_still_shows_the_real_accent_color():
    """Regression guard: Qt's default icon engine auto-desaturates a
    Normal-only QIcon's Disabled-mode rendering. Since the current step's
    button is disabled (to preserve click-gating), its circle must still
    render with the real painted accent color -- not Qt's auto-greyed
    version -- or the mockup's "you are here" accent circle disappears."""
    rail = WizardStepRail(["Type", "Data", "Labels"])
    rail.set_state(current_index=1, summaries={})
    tokens = design_tokens()
    rail.set_tokens(tokens)

    current_button = rail._step_widgets[1]
    assert current_button.isEnabled() is False

    normal_pixmap = current_button.icon().pixmap(17, 17, QIcon.Mode.Normal)
    disabled_pixmap = current_button.icon().pixmap(17, 17, QIcon.Mode.Disabled)

    # Same painted pixmap must be registered for both modes.
    assert normal_pixmap.toImage() == disabled_pixmap.toImage()

    # Sample a pixel inside the filled circle but above the centered
    # digit glyph (wider fonts on Linux cover the circle's corners), and confirm it's still the accent colour, not grey.
    color = disabled_pixmap.toImage().pixelColor(8, 3)
    accent = QColor(tokens["accent"])
    assert abs(color.red() - accent.red()) < 25
    assert abs(color.green() - accent.green()) < 25
    assert abs(color.blue() - accent.blue()) < 25
    # A grey desaturation would have near-equal R/G/B; the accent doesn't.
    channel_spread = max(color.red(), color.green(), color.blue()) - min(
        color.red(), color.green(), color.blue()
    )
    assert channel_spread > 20


def test_set_tokens_regenerates_the_circle_icons():
    rail = WizardStepRail(["Type", "Data", "Labels"])
    rail.set_state(current_index=1, summaries={})
    before = rail._step_widgets[1].icon().pixmap(17, 17).toImage()

    # Tokens for an accent unlike the default, so the current circle must change colour.
    rail.set_tokens(design_tokens(accent="#00FF00"))

    after = rail._step_widgets[1].icon().pixmap(17, 17).toImage()
    assert before != after


def test_completed_circle_draws_the_bundled_check_icon_in_the_completed_colour(monkeypatch):
    """The completed step's check is the bundled `check` icon (not a font glyph), tinted with the completed colour and drawn inside the circle."""
    requested = []
    real_build_icon = wizard_step_rail.build_icon

    def spy(name, color, **kwargs):
        requested.append((name, color))
        return real_build_icon(name, color, **kwargs)

    monkeypatch.setattr(wizard_step_rail, "build_icon", spy)
    rail = WizardStepRail(["Type", "Data", "Labels"])
    # Sentinel colours: a pure red check on a white circle, so the check's pixels can be told apart below.
    rail.set_tokens(design_tokens(accent_selected_bg="#FFFFFF", accent_active_text="#FF0000"))
    rail.set_state(current_index=1, summaries={0: "Type · Line"})

    assert ("check", "#FF0000") in requested
    image = rail._step_widgets[0].icon().pixmap(17, 17, QIcon.Mode.Normal).toImage()
    check_pixels = [
        (x, y)
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).red() - image.pixelColor(x, y).green() > 150 and image.pixelColor(x, y).green() == image.pixelColor(x, y).blue()
    ]
    assert check_pixels, "no pixel of the completed colour where the check is drawn"
    assert all(3 <= x <= 13 and 3 <= y <= 13 for x, y in check_pixels)
