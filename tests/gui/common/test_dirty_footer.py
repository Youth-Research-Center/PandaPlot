import pytest
from PySide6.QtWidgets import QApplication, QWidget

from pandaplot.gui.components.common.dirty_footer import DirtyFooter, format_status_text
from tests.gui.theme_testing import design_tokens

MODIFIED_SENTINEL = "#AA0000"
MUTED_SENTINEL = "#00BB00"


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _distinct_status_tokens() -> dict:
    """Real tokens whose modified and muted status colours are unmistakable sentinels, so the test can tell them apart."""
    return design_tokens(status_modified_text=MODIFIED_SENTINEL, text_hint=MUTED_SENTINEL)


def test_format_status_text_no_changes():
    assert format_status_text(is_modified=False, change_count=0) == "No changes"


def test_format_status_text_single_change():
    assert format_status_text(is_modified=True, change_count=1) == "Modified"


def test_format_status_text_multiple_changes():
    assert format_status_text(is_modified=True, change_count=3) == "3 unsaved changes"


def test_set_modified_false_disables_apply_and_revert():
    footer = DirtyFooter()
    footer.setModified(is_modified=False, change_count=0)
    assert not footer._apply_button.isEnabled()
    assert not footer._revert_button.isEnabled()


def test_set_modified_true_enables_apply_and_revert():
    footer = DirtyFooter()
    footer.setModified(is_modified=True, change_count=2)
    assert footer._apply_button.isEnabled()
    assert footer._revert_button.isEnabled()
    assert footer._status_label.text() == "2 unsaved changes"


def test_apply_button_click_emits_apply_clicked():
    footer = DirtyFooter()
    footer.setModified(is_modified=True, change_count=1)
    seen = []
    footer.applyClicked.connect(lambda: seen.append(True))
    footer._apply_button.click()
    assert seen == [True]


def test_revert_button_click_emits_revert_clicked():
    footer = DirtyFooter()
    footer.setModified(is_modified=True, change_count=1)
    seen = []
    footer.revertClicked.connect(lambda: seen.append(True))
    footer._revert_button.click()
    assert seen == [True]


def test_set_modified_true_with_zero_changes_disables_buttons():
    footer = DirtyFooter()
    footer.setModified(is_modified=True, change_count=0)
    assert not footer._apply_button.isEnabled()
    assert not footer._revert_button.isEnabled()
    assert footer._status_label.text() == "No changes"


def test_set_modified_refreshes_status_color_from_last_tokens():
    """The status color used to be set only in set_tokens(), so the label
    stayed muted after an edit (and amber after Apply/Revert) until the
    next theme change."""
    footer = DirtyFooter()
    footer.set_tokens(_distinct_status_tokens())
    assert MUTED_SENTINEL in footer._status_label.styleSheet()

    footer.setModified(is_modified=True, change_count=2)
    assert MODIFIED_SENTINEL in footer._status_label.styleSheet()

    footer.setModified(is_modified=False, change_count=0)
    assert MUTED_SENTINEL in footer._status_label.styleSheet()


def test_status_color_stays_modified_while_an_ancestor_is_disabled():
    """isEnabled() is False for every child of a disabled ancestor, so
    deriving "modified" from the Apply button's enabled state painted pending
    changes in the muted color whenever the panel was temporarily disabled."""
    parent = QWidget()
    footer = DirtyFooter(parent)
    footer.set_tokens(_distinct_status_tokens())
    parent.setEnabled(False)

    footer.setModified(is_modified=True, change_count=2)

    assert MODIFIED_SENTINEL in footer._status_label.styleSheet()
