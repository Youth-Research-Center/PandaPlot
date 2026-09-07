from unittest.mock import patch

import pytest
from PySide6.QtCore import QBuffer, QIODevice, QRect
from PySide6.QtGui import QImage

from pandaplot.app import build_app_context
from pandaplot.gui.dialogs.image.image_editor_dialog import ImageEditorDialog
from pandaplot.models.project.items import Image


def _make_test_image_bytes(width: int = 100, height: int = 80) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(0x00FF00)
    img.save(buffer, "PNG")
    return bytes(buffer.data())


class TestImageEditorDialog:
    def test_dialog_init_and_operations(self, qapp):
        app_context = build_app_context()
        orig_bytes = _make_test_image_bytes(100, 80)
        image = Image(id="test-img", name="Test Photo", width=100, height=80, image_ext="png")

        dialog = ImageEditorDialog(app_context, image, orig_bytes)

        assert dialog.spin_width.value() == 100
        assert dialog.spin_height.value() == 80

        # Rotate 90
        dialog._rotate(90)
        assert dialog.working_qimage.width() == 80
        assert dialog.working_qimage.height() == 100

        # Crop
        dialog.spin_crop_x.setValue(10)
        dialog.spin_crop_y.setValue(10)
        dialog.spin_crop_w.setValue(40)
        dialog.spin_crop_h.setValue(30)
        dialog._apply_crop()

        assert dialog.working_qimage.width() == 40
        assert dialog.working_qimage.height() == 30

        # Resize
        dialog.chk_keep_aspect.setChecked(False)
        dialog.spin_width.setValue(200)
        dialog.spin_height.setValue(150)
        dialog._apply_resize()

        assert dialog.working_qimage.width() == 200
        assert dialog.working_qimage.height() == 150

        # Reset
        dialog._reset_edits()
        assert dialog.working_qimage.width() == 100
        assert dialog.working_qimage.height() == 80

        res_bytes = dialog.get_result_bytes()
        assert isinstance(res_bytes, bytes)
        assert len(res_bytes) > 0


class TestImageEditorDialogFormatPreservation:
    def test_preserves_supported_bmp_extension(self, qapp):
        app_context = build_app_context()
        image = Image(id="fmt-bmp", name="Photo", width=10, height=10, image_ext="bmp")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(10, 10))

        assert dialog.get_result_ext() == "bmp"
        assert len(dialog.get_result_bytes()) > 0

    def test_falls_back_to_png_for_unsupported_extension(self, qapp, monkeypatch):
        from PySide6.QtGui import QImageWriter

        monkeypatch.setattr(
            QImageWriter, "supportedImageFormats",
            staticmethod(lambda: [b"PNG", b"JPEG", b"BMP"]),
        )
        app_context = build_app_context()
        image = Image(id="fmt-webp", name="Photo", width=10, height=10, image_ext="webp")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(10, 10))

        assert dialog.get_result_ext() == "png"
        assert len(dialog.get_result_bytes()) > 0

    def test_preserves_a_writable_extension_not_in_the_alias_map(self, qapp, monkeypatch):
        from PySide6.QtGui import QImageWriter

        # tiff isn't jpg/jpeg, so it's not in _EXT_ALIASES -- it should still
        # be preserved (derived as "TIFF" from the extension itself) as long
        # as the local Qt build can actually write it, rather than being
        # forced to png just for being absent from a fixed alias list.
        monkeypatch.setattr(
            QImageWriter, "supportedImageFormats",
            staticmethod(lambda: [b"png", b"jpeg", b"bmp", b"tiff"]),
        )
        app_context = build_app_context()
        image = Image(id="fmt-tiff", name="Photo", width=10, height=10, image_ext="tiff")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(10, 10))

        assert dialog.get_result_ext() == "tiff"
        assert len(dialog.get_result_bytes()) > 0


class TestImageEditorDialogCropClamping:
    def test_out_of_bounds_crop_spinbox_values_are_clamped_back(self, qapp):
        app_context = build_app_context()
        image = Image(id="clamp-1", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog.spin_crop_x.setValue(90)
        dialog.spin_crop_w.setValue(50)  # would extend to x=140, past the 100px-wide image

        assert dialog.spin_crop_w.value() == 10  # clamped to what actually fits: 100 - 90
        assert dialog.spin_crop_x.value() == 90

    def test_resize_spinboxes_raise_their_ceiling_for_an_oversized_image(self, qapp):
        # An image wider than the spinboxes' fixed 20000px construction-time
        # maximum must not have that width silently clamped down by
        # setValue() itself when _sync_control_values() reports it -- that
        # would show the wrong size and shrink the image on the next Apply
        # Resize. Kept 1px tall so the QImage allocation stays tiny.
        from PySide6.QtGui import QImage

        app_context = build_app_context()
        image = Image(id="oversized-1", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog.working_qimage = QImage(20005, 1, QImage.Format.Format_RGB32)
        dialog._sync_control_values()

        assert dialog.spin_width.value() == 20005
        assert dialog.spin_width.maximum() >= 20005

    def test_sync_control_values_does_not_trigger_reentrant_crop_clamping(self, qapp):
        from PySide6.QtCore import QRect

        app_context = build_app_context()
        image = Image(id="clamp-2", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        # Leave the crop spinboxes holding a rect (x=60, y=55, w=30, h=20) that
        # fits the *current* 100x80 image. When _apply_crop() crops the working
        # image down to exactly that 30x20 region and calls
        # _sync_control_values(), the ranges are updated to the new image's
        # bounds (x in [0,29], y in [0,19], w in [1,30], h in [1,20]) before the
        # values are rewritten. The stale x=60 (still sitting in the spinbox)
        # genuinely falls outside its new [0,29] range, so setRange() itself
        # would silently clamp it and emit valueChanged -- without the
        # re-entrancy guard around that setRange step, that would re-enter
        # _on_crop_spinbox_changed with a stale, partially-updated rect,
        # producing an extra, spurious write-back before the one legitimate
        # write _sync_control_values() itself makes at the end.
        dialog.spin_crop_x.setValue(60)
        dialog.spin_crop_y.setValue(55)
        dialog.spin_crop_w.setValue(30)
        dialog.spin_crop_h.setValue(20)

        write_calls: list[object] = []
        original_write = dialog._write_crop_spinboxes

        def spy(rect):
            write_calls.append(rect)
            return original_write(rect)

        dialog._write_crop_spinboxes = spy

        dialog._apply_crop()

        # Exactly the one legitimate write _sync_control_values() makes at the
        # end, with the correct final rect -- no earlier, spurious reentrant
        # write-back triggered by setRange() clamping stale values.
        assert write_calls == [QRect(0, 0, 30, 20)]
        assert dialog.spin_crop_x.value() == 0
        assert dialog.spin_crop_y.value() == 0
        assert dialog.spin_crop_w.value() == 30
        assert dialog.spin_crop_h.value() == 20


class TestImageEditorDialogCropCanvasSync:
    def test_dragging_canvas_rect_updates_spinboxes(self, qapp):
        from PySide6.QtCore import QRect

        app_context = build_app_context()
        image = Image(id="sync-1", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog.crop_canvas.cropRectChanged.emit(QRect(10, 5, 40, 30))

        assert dialog.spin_crop_x.value() == 10
        assert dialog.spin_crop_y.value() == 5
        assert dialog.spin_crop_w.value() == 40
        assert dialog.spin_crop_h.value() == 30

    def test_editing_spinbox_updates_canvas_rect(self, qapp):
        from PySide6.QtCore import QRect

        app_context = build_app_context()
        image = Image(id="sync-2", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog.spin_crop_x.setValue(15)
        dialog.spin_crop_w.setValue(20)

        assert dialog.crop_canvas.crop_rect() == QRect(15, 0, 20, 80)

    def test_rotate_resets_canvas_crop_rect_to_new_full_bounds(self, qapp):
        from PySide6.QtCore import QRect

        app_context = build_app_context()
        image = Image(id="sync-3", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog._rotate(90)

        assert dialog.crop_canvas.crop_rect() == QRect(0, 0, 80, 100)

    def test_aspect_preset_locks_canvas_and_reflows_current_rect(self, qapp):
        app_context = build_app_context()
        image = Image(id="sync-4", name="Photo", width=200, height=200, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(200, 200))
        dialog.spin_crop_w.setValue(100)
        dialog.spin_crop_h.setValue(100)

        index = dialog.aspect_combo.findText("1:1")
        dialog.aspect_combo.setCurrentIndex(index)

        assert dialog.crop_canvas._aspect_lock == pytest.approx(1.0)

        index_16_9 = dialog.aspect_combo.findText("16:9")
        dialog.aspect_combo.setCurrentIndex(index_16_9)

        assert dialog.crop_canvas._aspect_lock == pytest.approx(16 / 9)
        assert dialog.spin_crop_h.value() == round(dialog.spin_crop_w.value() / (16 / 9))


class TestImageEditorDialogUndoRedo:
    def test_undo_reverts_last_rotate(self, qapp):
        app_context = build_app_context()
        image = Image(id="undo-1", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog._rotate(90)
        assert dialog.working_qimage.width() == 80

        dialog._undo()

        assert dialog.working_qimage.width() == 100
        assert dialog.working_qimage.height() == 80

    def test_redo_reapplies_undone_rotate(self, qapp):
        app_context = build_app_context()
        image = Image(id="undo-2", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog._rotate(90)
        dialog._undo()
        dialog._redo()

        assert dialog.working_qimage.width() == 80
        assert dialog.working_qimage.height() == 100

    def test_new_op_after_undo_clears_redo_stack(self, qapp):
        app_context = build_app_context()
        image = Image(id="undo-3", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog._rotate(90)
        dialog._undo()
        dialog._rotate(180)

        assert dialog.btn_redo.isEnabled() is False

    def test_undo_button_disabled_with_empty_stack(self, qapp):
        app_context = build_app_context()
        image = Image(id="undo-4", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        assert dialog.btn_undo.isEnabled() is False

        dialog._rotate(90)

        assert dialog.btn_undo.isEnabled() is True

    def test_reset_all_edits_is_itself_undoable(self, qapp):
        app_context = build_app_context()
        image = Image(id="undo-5", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog._rotate(90)
        dialog._reset_edits()
        assert dialog.working_qimage.width() == 100

        dialog._undo()

        assert dialog.working_qimage.width() == 80
        assert dialog.working_qimage.height() == 100


class TestImageEditorDialogAspectLockSurvivesCommitsAndRotation:
    def test_lock_survives_a_commit_that_resets_canvas_to_full_bounds(self, qapp):
        """Finding #3a: every commit calls _sync_control_values(), which
        resets the canvas rect to full bounds via set_image() -- an active
        aspect lock must be reflowed back onto that reset rect rather than
        silently dropped."""
        from PySide6.QtCore import QRect

        app_context = build_app_context()
        image = Image(id="lock-1", name="Photo", width=200, height=100, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(200, 100))

        index = dialog.aspect_combo.findText("1:1")
        dialog.aspect_combo.setCurrentIndex(index)
        assert dialog.crop_canvas.aspect_lock() == pytest.approx(1.0)

        dialog._apply_resize()  # a resize with the same 200x100 size is a no-op commit

        rect = dialog.crop_canvas.crop_rect()
        assert rect.width() / rect.height() == pytest.approx(1.0)
        assert rect != QRect(0, 0, 200, 100)  # actually reflowed, not just full (non-square) bounds

    def test_original_lock_re_resolves_to_new_ratio_after_rotate(self, qapp):
        """Finding #3b: "Original" must mean "the current working image's
        ratio" even after a rotate changes that ratio, not the ratio at the
        moment "Original" was selected."""
        app_context = build_app_context()
        image = Image(id="lock-2", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        index = dialog.aspect_combo.findText("Original")
        dialog.aspect_combo.setCurrentIndex(index)
        assert dialog.crop_canvas.aspect_lock() == pytest.approx(100 / 80)

        dialog._rotate(90)  # working image is now 80x100

        assert dialog.crop_canvas.aspect_lock() == pytest.approx(80 / 100)

    def test_spinbox_edit_while_locked_reflows_to_lock(self, qapp):
        """Finding #3c: editing a crop spinbox while a lock is active must
        reflow the result back onto the lock, not just clamp to bounds.

        Asserting only width == height here would pass vacuously if the
        edit were silently discarded (both dimensions unchanged at 200), so
        this also asserts the height actually took on the edited value."""
        app_context = build_app_context()
        image = Image(id="lock-3", name="Photo", width=200, height=200, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(200, 200))

        index = dialog.aspect_combo.findText("1:1")
        dialog.aspect_combo.setCurrentIndex(index)

        # Editing height alone to a value that would violate the 1:1 lock.
        dialog.spin_crop_h.setValue(50)

        rect = dialog.crop_canvas.crop_rect()
        assert rect.height() == 50  # the edit must actually take effect
        assert rect.width() == 50  # width re-derived from the new height
        assert dialog.spin_crop_w.value() == dialog.spin_crop_h.value() == 50

    def test_spinbox_edit_height_with_locked_ratio_derives_width_from_height(self, qapp):
        """Finding #2 (re-review): editing spin_crop_h specifically while an
        aspect lock is active must derive width from the *new* height,
        rather than the lock's default width-drives-height reflow silently
        overwriting the height edit back to match the unchanged width. A
        non-1:1 ratio makes this direction distinguishable from the
        (unaffected) opposite bug."""
        app_context = build_app_context()
        image = Image(id="lock-3b", name="Photo", width=200, height=200, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(200, 200))

        index = dialog.aspect_combo.findText("16:9")
        dialog.aspect_combo.setCurrentIndex(index)

        dialog.spin_crop_h.setValue(40)

        rect = dialog.crop_canvas.crop_rect()
        assert rect.height() == 40
        assert rect.width() == round(40 * (16 / 9))
        assert dialog.spin_crop_h.value() == 40
        assert dialog.spin_crop_w.value() == round(40 * (16 / 9))


class TestImageEditorDialogNoOpCropSkipsUndoAndCopy:
    def test_apply_crop_with_full_bounds_rect_is_a_no_op(self, qapp):
        """Finding #6: a crop rect equal to the current full image bounds
        must not push an undo snapshot or copy the image."""
        app_context = build_app_context()
        image = Image(id="noop-crop", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        original_qimage = dialog.working_qimage
        assert dialog.btn_undo.isEnabled() is False

        dialog._apply_crop()  # spinboxes already describe the full image

        assert dialog.btn_undo.isEnabled() is False
        assert dialog.working_qimage is original_qimage


class TestImageEditorDialogNoOpResizeSkipsUndo:
    def test_apply_resize_with_unchanged_dimensions_is_a_no_op(self, qapp):
        """Applying the current dimensions as a resize target must not push
        an undo snapshot or append a (lossy) ResizeOp -- it changes no
        pixels."""
        app_context = build_app_context()
        image = Image(id="noop-resize", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        original_qimage = dialog.working_qimage
        assert dialog.btn_undo.isEnabled() is False

        dialog.chk_keep_aspect.setChecked(False)
        dialog.spin_width.setValue(dialog.working_qimage.width())
        dialog.spin_height.setValue(dialog.working_qimage.height())
        dialog._apply_resize()

        assert dialog.btn_undo.isEnabled() is False
        assert dialog.working_qimage is original_qimage

    def test_apply_resize_over_the_pixel_budget_warns_and_does_not_apply(self, qapp, monkeypatch):
        """A resize target whose *product* of width and height exceeds the
        pixel budget must be rejected with an actionable warning, even
        though each dimension individually fits the spinboxes' own
        20000px maximum (e.g. 15000x15000 = 225 megapixels)."""
        from PySide6.QtWidgets import QMessageBox

        app_context = build_app_context()
        image = Image(id="oversized-resize", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        original_qimage = dialog.working_qimage
        dialog.chk_keep_aspect.setChecked(False)
        dialog.spin_width.setValue(15000)
        dialog.spin_height.setValue(15000)

        with patch.object(QMessageBox, "warning") as mock_warning:
            dialog._apply_resize()

        mock_warning.assert_called_once()
        assert dialog.btn_undo.isEnabled() is False
        assert dialog.working_qimage is original_qimage


class TestImageEditorDialogMaintainAspectRaisesCompanionCeiling:
    def test_width_edit_raises_height_ceiling_for_extreme_aspect_image(self, qapp):
        """For an extreme-aspect image, the derived companion dimension can
        exceed the other spinbox's current maximum -- without raising that
        ceiling first, setValue() would silently clamp it, producing a
        distorted (non-aspect-locked) target despite "Maintain aspect
        ratio" being checked. A 1x20000 image changed to width=2 derives
        height=40000, which must not get clamped down to spin_height's
        prior 20000 maximum."""
        app_context = build_app_context()
        image = Image(id="extreme-aspect-w", name="Photo", width=1, height=20000, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(1, 20000))

        dialog.chk_keep_aspect.setChecked(True)
        dialog.spin_width.setValue(2)

        assert dialog.spin_height.value() == 40000

    def test_height_edit_raises_width_ceiling_for_extreme_aspect_image(self, qapp):
        """Symmetric to the width-edit case above: a 20000x1 image changed
        to height=2 derives width=40000."""
        app_context = build_app_context()
        image = Image(id="extreme-aspect-h", name="Photo", width=20000, height=1, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(20000, 1))

        dialog.chk_keep_aspect.setChecked(True)
        dialog.spin_height.setValue(2)

        assert dialog.spin_width.value() == 40000


class TestImageEditorDialogNoOpResetSkipsUndo:
    def test_reset_with_no_prior_edits_is_a_no_op(self, qapp):
        """Resetting an already-original image must not push an undo
        snapshot -- it changes no pixels and there's nothing to undo back
        to, unlike a reset that follows real edits."""
        app_context = build_app_context()
        image = Image(id="noop-reset", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        original_qimage = dialog.working_qimage
        assert dialog.btn_undo.isEnabled() is False

        dialog._reset_edits()

        assert dialog.btn_undo.isEnabled() is False
        assert dialog.working_qimage is original_qimage

    def test_reset_after_real_edits_still_pushes_undo(self, qapp):
        """A reset that actually discards edits must remain undoable --
        only a reset with nothing to discard is skipped."""
        app_context = build_app_context()
        image = Image(id="noop-reset-2", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog._rotate(90)
        dialog._reset_edits()

        assert dialog.btn_undo.isEnabled() is True
        dialog._undo()
        assert dialog.working_qimage.width() == 80
        assert dialog.working_qimage.height() == 100


class TestImageEditorDialogHasEdits:
    def test_fresh_dialog_has_no_edits(self, qapp):
        app_context = build_app_context()
        image = Image(id="has-edits-fresh", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        assert dialog.has_edits() is False

    def test_dialog_has_edits_after_a_rotate(self, qapp):
        app_context = build_app_context()
        image = Image(id="has-edits-rotate", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog._rotate(90)

        assert dialog.has_edits() is True

    def test_dialog_has_no_edits_after_reset(self, qapp):
        app_context = build_app_context()
        image = Image(id="has-edits-reset", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog._rotate(90)
        assert dialog.has_edits() is True

        dialog._reset_edits()

        assert dialog.has_edits() is False


class TestImageEditorDialogGetResultBytesSaveFailure:
    def test_get_result_bytes_raises_when_save_fails(self, qapp, monkeypatch):
        """Finding #13: a failed QImage.save() must not silently yield empty
        bytes -- that would get persisted as the image's new content."""
        app_context = build_app_context()
        image = Image(id="save-fail", name="Photo", width=10, height=10, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(10, 10))

        monkeypatch.setattr(QImage, "save", lambda self, *args, **kwargs: False)

        with pytest.raises(Exception):
            dialog.get_result_bytes()


class TestImageEditorDialogRedoShortcut:
    def test_ctrl_shift_z_also_triggers_redo(self, qapp):
        """Finding #11: Ctrl+Shift+Z must work as an additional redo binding
        alongside Ctrl+Y."""
        from PySide6.QtGui import QKeySequence, QShortcut

        app_context = build_app_context()
        image = Image(id="redo-shortcut", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        shortcuts = dialog.findChildren(QShortcut)
        sequences = [s.key() for s in shortcuts]
        assert QKeySequence("Ctrl+Shift+Z") in sequences


class TestImageEditorDialogEndToEndFlow:
    def test_full_crop_lock_rotate_undo_export_flow(self, qapp):
        """Finding #17/#18/#19: a realistic full sequence through the
        dialog -- set a crop rect via the canvas, lock an aspect ratio,
        rotate, undo, then export -- asserting sane state at each step.
        This is the kind of test that would have directly caught findings
        #2 and #3 (aspect lock silently violated at the image boundary and
        after a commit)."""
        from PySide6.QtCore import QRect

        app_context = build_app_context()
        image = Image(id="e2e-1", name="Photo", width=200, height=100, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(200, 100))

        # 1. Drag/set a crop rect directly on the canvas (as a real drag
        # would, via the cropRectChanged signal the canvas emits).
        dialog.crop_canvas.cropRectChanged.emit(QRect(10, 10, 150, 70))
        dialog.crop_canvas.set_crop_rect(QRect(10, 10, 150, 70))
        assert dialog.crop_canvas.crop_rect() == QRect(10, 10, 150, 70)
        assert dialog.spin_crop_w.value() == 150
        assert dialog.spin_crop_h.value() == 70

        # 2. Lock an aspect ratio -- reflows the current rect to match.
        index = dialog.aspect_combo.findText("1:1")
        dialog.aspect_combo.setCurrentIndex(index)
        locked_rect = dialog.crop_canvas.crop_rect()
        assert locked_rect.width() == locked_rect.height()

        # 3. Rotate -- the canvas resets to the new full bounds, but the
        #    lock (still active) must be reflowed onto it, and stay a valid
        #    ratio for the new orientation too (finding #3a).
        dialog._rotate(90)
        assert dialog.working_qimage.width() == 100
        assert dialog.working_qimage.height() == 200
        post_rotate_rect = dialog.crop_canvas.crop_rect()
        assert post_rotate_rect.width() == post_rotate_rect.height()
        assert post_rotate_rect.width() <= 100
        assert post_rotate_rect.height() <= 200

        # 4. Undo the rotate -- canvas must reflect the restored image's
        #    full bounds (finding #18), not stale post-rotate bounds.
        dialog._undo()
        assert dialog.working_qimage.width() == 200
        assert dialog.working_qimage.height() == 100
        undone_rect = dialog.crop_canvas.crop_rect()
        assert undone_rect.width() <= 200
        assert undone_rect.height() <= 100

        # 5. Export -- sane, non-empty result reflecting the current image.
        result_bytes = dialog.get_result_bytes()
        assert isinstance(result_bytes, bytes)
        assert len(result_bytes) > 0
        assert dialog.get_result_width() == 200
        assert dialog.get_result_height() == 100


class TestImageEditorDialogUndoRestoresCanvasBounds:
    def test_undo_after_crop_restores_canvas_to_pre_crop_full_bounds(self, qapp):
        """Finding #18: after undo, crop_canvas.crop_rect() must reflect the
        restored image's full bounds, not stale bounds from the undone
        (cropped) state."""
        from PySide6.QtCore import QRect

        app_context = build_app_context()
        image = Image(id="undo-canvas-1", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog.spin_crop_x.setValue(10)
        dialog.spin_crop_y.setValue(10)
        dialog.spin_crop_w.setValue(40)
        dialog.spin_crop_h.setValue(30)
        dialog._apply_crop()
        assert dialog.crop_canvas.crop_rect() == QRect(0, 0, 40, 30)

        dialog._undo()

        assert dialog.working_qimage.width() == 100
        assert dialog.working_qimage.height() == 80
        assert dialog.crop_canvas.crop_rect() == QRect(0, 0, 100, 80)


class TestImageEditorDialogTransformBasedUndoRedo:
    def test_undo_redo_stacks_hold_transform_lists_not_images(self, qapp):
        from pandaplot.gui.dialogs.image.image_transforms import CropOp, ResizeOp, RotateOp

        app_context = build_app_context()
        image = Image(id="txn-1", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog._rotate(90)
        # Aspect lock defaults on, and would otherwise cascade the height
        # edit below back into the width spinbox (mirroring
        # _on_height_changed), silently producing a different ResizeOp than
        # the one explicitly requested here.
        dialog.chk_keep_aspect.setChecked(False)
        dialog.spin_width.setValue(40)
        dialog.spin_height.setValue(30)
        dialog._apply_resize()
        dialog.spin_crop_x.setValue(5)
        dialog.spin_crop_y.setValue(5)
        dialog.spin_crop_w.setValue(20)
        dialog.spin_crop_h.setValue(15)
        dialog._apply_crop()

        assert len(dialog._undo_stack) == 3
        for snapshot in dialog._undo_stack:
            assert isinstance(snapshot, list)
            for entry in snapshot:
                assert isinstance(entry, (RotateOp, ResizeOp, CropOp))
        assert dialog._transforms == [
            RotateOp(90), ResizeOp(40, 30), CropOp(QRect(5, 5, 20, 15)),
        ]

    def test_redo_after_undo_matches_a_fresh_replay_of_the_same_final_state(self, qapp):
        from pandaplot.gui.dialogs.image.image_transforms import replay_transforms

        app_context = build_app_context()
        image = Image(id="txn-2", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog._rotate(90)
        dialog.spin_width.setValue(40)
        dialog.spin_height.setValue(30)
        dialog._apply_resize()
        dialog._rotate(180)

        # Undo twice, then redo twice. Both undo and redo rebuild via
        # replay_transforms (redo no longer takes a "direct apply the last
        # transform" shortcut -- that shortcut assumed the popped redo
        # entry was always exactly one transform longer than the current
        # list, which doesn't hold once a reset is in the history; see
        # test_redo_after_undoing_a_reset_does_not_crash).
        dialog._undo()
        dialog._undo()
        dialog._redo()
        dialog._redo()

        # The undo/redo round-trip must land bit-identical to a fresh
        # from-scratch replay of the same final transform list.
        expected = replay_transforms(dialog.original_qimage, dialog._transforms)
        assert dialog.working_qimage == expected

    def test_redo_after_undoing_a_reset_does_not_crash(self, qapp):
        """Finding #1: rotate -> reset -> undo -> redo used to raise
        IndexError. _reset_edits pushes the pre-reset transform list (here,
        [RotateOp(90)]) onto the undo stack and sets self._transforms = [].
        Undoing pops that back and pushes [] onto the redo stack. Redoing
        then used to assume the popped redo entry ([]) was always exactly
        one transform longer than the current list, with the new transform
        last -- and reached for restored[-1] on the empty list."""
        app_context = build_app_context()
        image = Image(id="txn-reset-1", name="Photo", width=100, height=80, image_ext="png")
        dialog = ImageEditorDialog(app_context, image, _make_test_image_bytes(100, 80))

        dialog._rotate(90)
        dialog._reset_edits()
        dialog._undo()
        dialog._redo()  # must not raise IndexError

        assert dialog._transforms == []
        assert dialog.working_qimage.width() == 100
        assert dialog.working_qimage.height() == 80
