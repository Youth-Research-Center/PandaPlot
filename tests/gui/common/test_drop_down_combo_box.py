"""The dropdown must open below its field, not over it.

On macOS a plain QComboBox opens its list on top of the field, centred on the
current item -- it reads as a menu appearing in the middle rather than as a
dropdown.
"""
import pytest
from PySide6.QtWidgets import QApplication, QListView, QVBoxLayout, QWidget

from pandaplot.gui.components.common.drop_down_combo_box import DropDownComboBox


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _host_with_combo(position=(200, 300)):
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = DropDownComboBox()
    combo.addItems(["Data", "First", "damped_pendulum_run_47", "Second"])
    combo.setCurrentIndex(2)
    layout.addWidget(combo)
    host.move(*position)
    host.resize(400, 120)
    host.show()
    QApplication.processEvents()
    return host, combo


def _popup_geometry(combo):
    popup = combo.view().window()
    return popup, popup.mapToGlobal(popup.rect().topLeft())


def test_uses_a_list_view_so_the_popup_can_be_placed():
    """The native menu-style popup container cannot be repositioned."""
    host, combo = _host_with_combo()
    try:
        view = combo.view()
        assert isinstance(view, QListView)
        # A plain QComboBox installs its own QComboBoxListView, which gets the native menu-style popup.
        assert view.metaObject().className() == "QListView"
    finally:
        host.close()


def test_popup_opens_directly_below_the_field():
    host, combo = _host_with_combo()
    try:
        combo.showPopup()
        QApplication.processEvents()

        _popup, popup_top_left = _popup_geometry(combo)
        field_bottom = combo.mapToGlobal(combo.rect().bottomLeft())

        assert popup_top_left.y() >= field_bottom.y() - 2
        assert popup_top_left.x() == field_bottom.x()
    finally:
        combo.hidePopup()
        host.close()


def test_popup_is_at_least_as_wide_as_the_field():
    host, combo = _host_with_combo()
    try:
        combo.showPopup()
        QApplication.processEvents()

        popup, _ = _popup_geometry(combo)
        assert popup.width() >= combo.width()
    finally:
        combo.hidePopup()
        host.close()


def test_popup_stays_on_screen_near_the_bottom_edge():
    """With no room below, the list must flip above rather than run off."""
    available = QApplication.primaryScreen().availableGeometry()
    host, combo = _host_with_combo(position=(200, available.bottom() - 130))
    try:
        combo.showPopup()
        QApplication.processEvents()

        popup, popup_top_left = _popup_geometry(combo)

        assert popup_top_left.y() >= available.top()
        assert popup_top_left.y() + popup.height() <= available.bottom() + 1
    finally:
        combo.hidePopup()
        host.close()
