import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.tabs.image.image_lightbox_dialog import ImageLightboxDialog
from pandaplot.models.project.items import Image


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _colored_pixmap(color: str) -> QPixmap:
    pixmap = QPixmap(10, 10)
    pixmap.fill(QColor(color))
    return pixmap


class TestImageLightboxDialogNavigation:
    def test_starts_at_given_index_with_matching_title(self):
        images = [Image(name="First"), Image(name="Second"), Image(name="Third")]
        dialog = ImageLightboxDialog(images, 1, load_pixmap=lambda img: _colored_pixmap("red"))

        assert dialog.windowTitle() == "Second"

    def test_previous_disabled_at_first_index(self):
        images = [Image(name="First"), Image(name="Second")]
        dialog = ImageLightboxDialog(images, 0, load_pixmap=lambda img: _colored_pixmap("red"))

        assert dialog.previous_button.isEnabled() is False
        assert dialog.next_button.isEnabled() is True

    def test_next_disabled_at_last_index(self):
        images = [Image(name="First"), Image(name="Second")]
        dialog = ImageLightboxDialog(images, 1, load_pixmap=lambda img: _colored_pixmap("red"))

        assert dialog.previous_button.isEnabled() is True
        assert dialog.next_button.isEnabled() is False

    def test_next_advances_index_and_title(self):
        images = [Image(name="First"), Image(name="Second")]
        dialog = ImageLightboxDialog(images, 0, load_pixmap=lambda img: _colored_pixmap("red"))

        dialog._go_next()

        assert dialog.windowTitle() == "Second"
        assert dialog.next_button.isEnabled() is False

    def test_previous_after_next_returns_to_start(self):
        images = [Image(name="First"), Image(name="Second"), Image(name="Third")]
        dialog = ImageLightboxDialog(images, 0, load_pixmap=lambda img: _colored_pixmap("red"))

        dialog._go_next()
        dialog._go_previous()

        assert dialog.windowTitle() == "First"

    def test_failed_load_shows_broken_placeholder_without_crashing(self):
        images = [Image(name="Broken")]

        def _failing_load(img):
            return None

        dialog = ImageLightboxDialog(images, 0, load_pixmap=_failing_load)

        assert dialog.image_label.pixmap() is not None
        assert not dialog.image_label.pixmap().isNull()


class TestImageLightboxDialogFixedSize:
    def test_dialog_size_unchanged_across_images_of_different_dimensions(self):
        small_pixmap = _colored_pixmap("red")  # 10x10, from existing test helper
        big_pixmap = QPixmap(2000, 1500)
        big_pixmap.fill(QColor("blue"))

        images = [Image(name="Small"), Image(name="Big")]
        pixmaps = {images[0].id: small_pixmap, images[1].id: big_pixmap}

        dialog = ImageLightboxDialog(images, 0, load_pixmap=lambda img: pixmaps[img.id])
        size_before = dialog.size()

        dialog._go_next()

        assert dialog.size() == size_before

    def test_first_shown_image_scales_to_initial_frame_not_default_label_size(self):
        # Regression test: a freshly-constructed QLabel that hasn't been
        # shown/laid out yet reports Qt's default widget size, QSize(640, 480)
        # -- NOT (0, 0) -- so _content_area_size() must not rely on the
        # label's reported size to detect "not laid out yet" for the very
        # first image. A 2000x1500 (4:3) pixmap scaled with KeepAspectRatio
        # into the initial content area (the dialog's fixed 1200x900 size,
        # minus the nav row's height, since the label only gets the
        # remaining vertical space in the QVBoxLayout) lands at that area's
        # exact size; if the bug regresses, it would instead scale to fit
        # Qt's default pre-layout QLabel size of 640x480.
        big_pixmap = QPixmap(2000, 1500)
        big_pixmap.fill(QColor("blue"))
        images = [Image(name="Big")]

        dialog = ImageLightboxDialog(images, 0, load_pixmap=lambda img: big_pixmap)

        nav_row_height = dialog.previous_button.sizeHint().height()
        expected_area = QSize(1200, 900 - nav_row_height)
        expected = big_pixmap.size().scaled(expected_area, Qt.AspectRatioMode.KeepAspectRatio)

        scaled = dialog.image_label.pixmap()
        assert scaled.width() == expected.width()
        assert scaled.height() == expected.height()

    def test_dialog_can_be_shrunk_by_user_after_showing(self, qapp):
        big_pixmap = QPixmap(2000, 1500)
        big_pixmap.fill(QColor("red"))
        images = [Image(name="First"), Image(name="Second")]
        dialog = ImageLightboxDialog(images, 0, load_pixmap=lambda img: big_pixmap)
        dialog.show()
        qapp.processEvents()

        dialog.resize(700, 600)
        qapp.processEvents()

        assert dialog.size().width() <= 750
        assert dialog.size().height() <= 650

    def test_long_title_is_elided(self):
        long_name = "vacation_photo_from_the_summer_trip_final_edited_version_2026_extra_long_suffix"
        images = [Image(name=long_name)]

        dialog = ImageLightboxDialog(images, 0, load_pixmap=lambda img: _colored_pixmap("red"))

        assert dialog.windowTitle() != long_name
        assert len(dialog.windowTitle()) < len(long_name)


class TestImageLightboxDialogEdit:
    def test_edit_button_hidden_without_on_edit_callback(self, qapp):
        # isVisible() only reflects real state once the dialog has actually
        # been shown (an un-shown QDialog reports every descendant as not
        # visible regardless of layout membership), so this needs a real
        # show()+processEvents() pass -- matching
        # test_dialog_can_be_shrunk_by_user_after_showing's convention above.
        images = [Image(name="First")]
        dialog = ImageLightboxDialog(images, 0, load_pixmap=lambda img: _colored_pixmap("red"))
        dialog.show()
        qapp.processEvents()

        assert dialog.edit_button.isVisible() is False

    def test_edit_button_present_with_on_edit_callback(self, qapp):
        images = [Image(name="First")]
        dialog = ImageLightboxDialog(
            images, 0, load_pixmap=lambda img: _colored_pixmap("red"), on_edit=lambda img: None
        )
        dialog.show()
        qapp.processEvents()

        assert dialog.edit_button.isVisible() is True

    def test_clicking_edit_invokes_callback_with_current_image_and_rerenders(self):
        images = [Image(name="First"), Image(name="Second")]
        received = []
        load_calls = []

        def _on_edit(img):
            received.append(img)

        def _load(img):
            load_calls.append(img)
            return _colored_pixmap("red")

        dialog = ImageLightboxDialog(images, 1, load_pixmap=_load, on_edit=_on_edit)

        # The constructor's own initial render already calls load_pixmap
        # once -- reset the spy so the count below reflects only the
        # re-render triggered by _trigger_edit() itself.
        load_calls.clear()

        dialog._trigger_edit()

        assert received == [images[1]]
        # _trigger_edit() must actually re-render (not just invoke the
        # callback) -- load_pixmap is the hook _render_current() uses to
        # fetch the image to display, so one more call after the edit
        # confirms a real re-render happened, not just the callback firing.
        assert load_calls == [images[1]]


class TestImageLightboxDialogSignatureOrder:
    def test_parent_can_still_be_passed_positionally_in_its_original_slot(self, qapp):
        """on_edit was added as a new parameter after load_pixmap in an
        earlier revision, ahead of the pre-existing parent parameter --
        which would silently break any positional caller expecting the
        4th positional argument to be parent (a QWidget passed there would
        instead be bound to on_edit, an Optional[Callable]). parent must
        stay in its original positional slot, with on_edit moved after it
        and made keyword-only."""
        from PySide6.QtWidgets import QWidget

        images = [Image(name="First")]
        host = QWidget()
        try:
            dialog = ImageLightboxDialog(images, 0, lambda img: _colored_pixmap("red"), host)
            assert dialog.parent() is host
            assert dialog._on_edit is None
        finally:
            host.deleteLater()

    def test_on_edit_is_keyword_only(self, qapp):
        images = [Image(name="First")]
        with pytest.raises(TypeError):
            ImageLightboxDialog(images, 0, lambda img: _colored_pixmap("red"), None, lambda img: None)
