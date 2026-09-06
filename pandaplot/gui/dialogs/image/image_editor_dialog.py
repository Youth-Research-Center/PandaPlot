"""
Dialog for basic image operations: crop, rotate, and resize.
"""

from typing import Optional, override

from PySide6.QtCore import QBuffer, QIODevice, QRect, Qt
from PySide6.QtGui import QImage, QImageWriter, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.gui.dialogs.image.crop_canvas import CropCanvas, clamp_rect_to_bounds
from pandaplot.gui.dialogs.image.image_transforms import (
    CropOp,
    ResizeOp,
    RotateOp,
    Transform,
    apply_transform,
    replay_transforms,
)
from pandaplot.models.project.items import Image
from pandaplot.models.state.app_context import AppContext

# Only extensions whose Qt format name isn't just their own uppercase form
# (i.e. real aliases) need an entry here -- anything else (bmp, gif, webp,
# tiff/tif, ...) is derived directly from the extension in
# _resolve_output_format, so a writable format never gets forced to PNG
# just because it's missing from a fixed list.
_EXT_ALIASES = {"jpg": "JPEG", "jpeg": "JPEG"}


class ImageEditorDialog(PDialog):
    """
    Dialog providing crop, rotate, and resize tools with live preview.
    """

    def __init__(self, app_context: AppContext, image: Image,
                 image_bytes: bytes, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.image_model = image
        self.original_bytes = image_bytes
        self.image_ext = (image.image_ext or "png").lower()

        # Load working QImage from original bytes
        self.original_qimage = QImage()
        self.original_qimage.loadFromData(self.original_bytes)
        self.working_qimage = QImage(self.original_qimage)

        self.aspect_ratio = (
            self.working_qimage.width() / self.working_qimage.height()
            if self.working_qimage.height() > 0 else 1.0
        )
        self._updating_resize_spinboxes = False
        self._updating_crop_spinboxes = False
        self._resolved_format: Optional[tuple[str, str]] = None
        self._transforms: list[Transform] = []
        self._undo_stack: list[list[Transform]] = []
        self._redo_stack: list[list[Transform]] = []

        self._initialize()
        self._update_info_label()
        self._sync_control_values()

    @override
    def _init_ui(self):
        self.setWindowTitle(f"Edit Image - {self.image_model.name}")
        self.resize(1000, 650)

        main_layout = QHBoxLayout(self)

        # Left side: Image preview area
        preview_container = QVBoxLayout()
        self.crop_canvas = CropCanvas()
        preview_container.addWidget(self.crop_canvas, stretch=1)

        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_container.addWidget(self.info_label)

        main_layout.addLayout(preview_container, stretch=2)

        # Right side: Control panel
        controls_layout = QVBoxLayout()

        # --- Rotate Box ---
        rotate_group = QGroupBox("Rotate")
        rotate_layout = QHBoxLayout(rotate_group)

        self.btn_rotate_ccw = PButton("↺ 90°", role="secondary", on_click=lambda: self._rotate(-90))
        self.btn_rotate_cw = PButton("↻ 90°", role="secondary", on_click=lambda: self._rotate(90))
        self.btn_rotate_180 = PButton("180°", role="secondary", on_click=lambda: self._rotate(180))

        rotate_layout.addWidget(self.btn_rotate_ccw)
        rotate_layout.addWidget(self.btn_rotate_cw)
        rotate_layout.addWidget(self.btn_rotate_180)
        controls_layout.addWidget(rotate_group)

        # --- Resize Box ---
        resize_group = QGroupBox("Resize")
        resize_layout = QVBoxLayout(resize_group)

        size_inputs_layout = QHBoxLayout()
        size_inputs_layout.addWidget(QLabel("Width:"))
        self.spin_width = QSpinBox()
        self.spin_width.setRange(1, 20000)
        size_inputs_layout.addWidget(self.spin_width)

        size_inputs_layout.addWidget(QLabel("Height:"))
        self.spin_height = QSpinBox()
        self.spin_height.setRange(1, 20000)
        size_inputs_layout.addWidget(self.spin_height)

        resize_layout.addLayout(size_inputs_layout)

        self.chk_keep_aspect = QCheckBox("Maintain aspect ratio")
        self.chk_keep_aspect.setChecked(True)
        resize_layout.addWidget(self.chk_keep_aspect)

        self.btn_apply_resize = PButton("Apply Resize", role="secondary", on_click=self._apply_resize)
        resize_layout.addWidget(self.btn_apply_resize)

        controls_layout.addWidget(resize_group)

        # --- Crop Box ---
        crop_group = QGroupBox("Crop")
        crop_layout = QVBoxLayout(crop_group)

        crop_grid = QHBoxLayout()
        crop_grid.addWidget(QLabel("X:"))
        self.spin_crop_x = QSpinBox()
        self.spin_crop_x.setRange(0, 20000)
        crop_grid.addWidget(self.spin_crop_x)

        crop_grid.addWidget(QLabel("Y:"))
        self.spin_crop_y = QSpinBox()
        self.spin_crop_y.setRange(0, 20000)
        crop_grid.addWidget(self.spin_crop_y)

        crop_layout.addLayout(crop_grid)

        crop_dim_grid = QHBoxLayout()
        crop_dim_grid.addWidget(QLabel("W:"))
        self.spin_crop_w = QSpinBox()
        self.spin_crop_w.setRange(1, 20000)
        crop_dim_grid.addWidget(self.spin_crop_w)

        crop_dim_grid.addWidget(QLabel("H:"))
        self.spin_crop_h = QSpinBox()
        self.spin_crop_h.setRange(1, 20000)
        crop_dim_grid.addWidget(self.spin_crop_h)

        crop_layout.addLayout(crop_dim_grid)

        aspect_row = QHBoxLayout()
        aspect_row.addWidget(QLabel("Aspect:"))
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(["Free", "1:1", "Original", "16:9", "4:3"])
        aspect_row.addWidget(self.aspect_combo)
        crop_layout.addLayout(aspect_row)

        self.btn_apply_crop = PButton("Apply Crop", role="secondary", on_click=self._apply_crop)
        crop_layout.addWidget(self.btn_apply_crop)

        controls_layout.addWidget(crop_group)

        # --- Revert & Dialog Action Buttons ---
        controls_layout.addStretch(1)

        undo_redo_row = QHBoxLayout()
        self.btn_undo = PButton("Undo", role="secondary", on_click=self._undo, enabled=False)
        self.btn_redo = PButton("Redo", role="secondary", on_click=self._redo, enabled=False)
        undo_redo_row.addWidget(self.btn_undo)
        undo_redo_row.addWidget(self.btn_redo)
        controls_layout.addLayout(undo_redo_row)

        self.btn_reset = PButton("Reset All Edits", role="secondary", on_click=self._reset_edits)
        controls_layout.addWidget(self.btn_reset)

        btn_box = QHBoxLayout()
        self.btn_cancel = PButton("Cancel", role="secondary", on_click=self.reject)
        self.btn_apply = PButton("Save Changes", role="primary", on_click=self.accept)
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_apply)

        controls_layout.addLayout(btn_box)

        main_layout.addLayout(controls_layout, stretch=1)

        # Connect signals
        self.spin_width.valueChanged.connect(self._on_width_changed)
        self.spin_height.valueChanged.connect(self._on_height_changed)
        # Each spinbox is wired through a small wrapper that tells the
        # shared handler which dimension it fired for -- needed so an
        # active aspect lock reflows in the correct direction (see
        # _on_crop_spinbox_changed / finding #2: a lock always deriving
        # height-from-width would silently discard an edit made directly
        # to the height spinbox).
        self.spin_crop_x.valueChanged.connect(lambda v: self._on_crop_spinbox_changed(v, "x"))
        self.spin_crop_y.valueChanged.connect(lambda v: self._on_crop_spinbox_changed(v, "y"))
        self.spin_crop_w.valueChanged.connect(lambda v: self._on_crop_spinbox_changed(v, "w"))
        self.spin_crop_h.valueChanged.connect(lambda v: self._on_crop_spinbox_changed(v, "h"))
        self.crop_canvas.cropRectChanged.connect(self._on_canvas_crop_rect_changed)
        self.aspect_combo.currentTextChanged.connect(self._on_aspect_changed)

        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self._redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self._redo)

    @override
    def _apply_theme(self):
        pass

    def _sync_control_values(self):
        w = self.working_qimage.width()
        h = self.working_qimage.height()
        self.aspect_ratio = w / h if h > 0 else 1.0

        self._updating_resize_spinboxes = True
        # Raise the ceiling to at least the current dimension first -- an
        # image wider/taller than the spinboxes' fixed 20000px maximum would
        # otherwise get silently clamped by setValue() itself, showing the
        # wrong size and shrinking the image on the next Apply Resize.
        # This ceiling is intentionally monotonic (it only ever grows, even
        # after a later resize/crop shrinks the image back down) -- it's a
        # permissive upper bound, not meant to track the image size exactly.
        # The spinbox's *value* is always overwritten to the correct current
        # size right below, so a stale/oversized ceiling is harmless. This is
        # unlike the crop spinboxes' ranges just below, which the
        # surrounding code does compute exactly from the current dimensions.
        self.spin_width.setRange(1, max(20000, w))
        self.spin_height.setRange(1, max(20000, h))
        self.spin_width.setValue(w)
        self.spin_height.setValue(h)
        self._updating_resize_spinboxes = False

        # set_image() unconditionally resets the canvas rect to the new
        # full bounds, ignoring any active aspect lock -- _reapply_current_
        # aspect_lock() below reflows that reset rect back to the currently
        # selected lock (a no-op if the selection is "Free").
        self.crop_canvas.set_image(self.working_qimage)

        # Guarded: a spinbox still holding a value from the *previous* image
        # size can get silently clamped by setRange() itself (e.g. the old
        # width no longer fits the new, narrower range), which emits
        # valueChanged and would otherwise re-enter _on_crop_spinbox_changed
        # with a stale, partially-updated rect before the real values below
        # are written.
        self._updating_crop_spinboxes = True
        self.spin_crop_x.setRange(0, max(0, w - 1))
        self.spin_crop_y.setRange(0, max(0, h - 1))
        self.spin_crop_w.setRange(1, w)
        self.spin_crop_h.setRange(1, h)
        self._updating_crop_spinboxes = False

        self._reapply_current_aspect_lock()
        self._write_crop_spinboxes(self.crop_canvas.crop_rect())

    def _update_info_label(self):
        self.info_label.setText(
            f"Current Size: {self.working_qimage.width()} × {self.working_qimage.height()} px"
        )

    def _on_width_changed(self, new_width: int):
        if self._updating_resize_spinboxes or not self.chk_keep_aspect.isChecked():
            return
        if self.aspect_ratio > 0:
            new_height = max(1, round(new_width / self.aspect_ratio))
            self._updating_resize_spinboxes = True
            self.spin_height.setValue(new_height)
            self._updating_resize_spinboxes = False

    def _on_height_changed(self, new_height: int):
        if self._updating_resize_spinboxes or not self.chk_keep_aspect.isChecked():
            return
        if self.aspect_ratio > 0:
            new_width = max(1, round(new_height * self.aspect_ratio))
            self._updating_resize_spinboxes = True
            self.spin_width.setValue(new_width)
            self._updating_resize_spinboxes = False

    def _push_undo_snapshot(self) -> None:
        self._undo_stack.append(list(self._transforms))
        self._redo_stack.clear()
        self._refresh_undo_redo_buttons()

    def _refresh_undo_redo_buttons(self) -> None:
        self.btn_undo.setEnabled(bool(self._undo_stack))
        self.btn_redo.setEnabled(bool(self._redo_stack))

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(list(self._transforms))
        self._transforms = self._undo_stack.pop()
        self.working_qimage = replay_transforms(self.original_qimage, self._transforms)
        self._sync_control_values()
        self._update_info_label()
        self._refresh_undo_redo_buttons()

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(list(self._transforms))
        # Rebuilt via a full replay from the original image, exactly like
        # _undo -- an earlier version applied only the last transform of
        # `restored` directly to the current working image, assuming
        # `restored` is always exactly one transform longer than
        # self._transforms with that one transform last. That assumption
        # doesn't hold once _reset_edits is in the history: a
        # rotate -> reset -> undo -> redo sequence pops an empty list as
        # `restored` (the pre-reset state, which was []), so `restored[-1]`
        # raised IndexError. Replaying from scratch has no such invariant
        # to violate.
        self._transforms = self._redo_stack.pop()
        self.working_qimage = replay_transforms(self.original_qimage, self._transforms)
        self._sync_control_values()
        self._update_info_label()
        self._refresh_undo_redo_buttons()

    def _rotate(self, degrees: int):
        self._push_undo_snapshot()
        transform = RotateOp(degrees)
        self.working_qimage = apply_transform(self.working_qimage, transform)
        self._transforms.append(transform)
        self._sync_control_values()
        self._update_info_label()

    def _apply_resize(self):
        target_w = self.spin_width.value()
        target_h = self.spin_height.value()
        if target_w <= 0 or target_h <= 0:
            return

        self._push_undo_snapshot()
        transform = ResizeOp(target_w, target_h)
        self.working_qimage = apply_transform(self.working_qimage, transform)
        self._transforms.append(transform)
        self._sync_control_values()
        self._update_info_label()

    def _clamp_crop_rect(self, rect: QRect) -> QRect:
        return clamp_rect_to_bounds(rect, self.working_qimage.width(), self.working_qimage.height())

    def _write_crop_spinboxes(self, rect: QRect) -> None:
        self._updating_crop_spinboxes = True
        self.spin_crop_x.setValue(rect.x())
        self.spin_crop_y.setValue(rect.y())
        self.spin_crop_w.setValue(rect.width())
        self.spin_crop_h.setValue(rect.height())
        self._updating_crop_spinboxes = False

    def _on_crop_spinbox_changed(self, _value: int, field: str = "w") -> None:
        if self._updating_crop_spinboxes:
            return
        rect = QRect(
            self.spin_crop_x.value(), self.spin_crop_y.value(),
            self.spin_crop_w.value(), self.spin_crop_h.value(),
        )
        clamped = self._clamp_crop_rect(rect)
        self.crop_canvas.set_crop_rect(clamped)
        # A spinbox edit doesn't go through the canvas's own drag-time lock
        # enforcement, so an active lock has to be reapplied explicitly here
        # -- otherwise editing a spinbox while locked could leave the canvas
        # rect (and the values written back below) violating the lock. When
        # the edit was specifically to the height spinbox, the reflow must
        # preserve that new height and derive width from it -- the default
        # width-drives-height reflow would otherwise silently overwrite the
        # user's height edit back to whatever height matches the unchanged
        # width.
        preserve = "height" if field == "h" else "width"
        self._reapply_current_aspect_lock(preserve=preserve)
        self._write_crop_spinboxes(self.crop_canvas.crop_rect())

    def _on_canvas_crop_rect_changed(self, rect: QRect) -> None:
        self._write_crop_spinboxes(rect)

    _ASPECT_RATIOS = {"1:1": 1.0, "16:9": 16 / 9, "4:3": 4 / 3}

    def _resolve_aspect_ratio_for_label(self, label: str) -> Optional[float]:
        """Resolves an aspect-combo label to a lock ratio (or None for
        "Free"). "Original" is resolved against self.aspect_ratio at call
        time (not memoized), so it always reflects the working image's
        *current* orientation -- important because it's re-resolved after
        every rotate, not just when the combo selection itself changes."""
        if label == "Free":
            return None
        if label == "Original":
            return self.aspect_ratio
        return self._ASPECT_RATIOS[label]

    def _on_aspect_changed(self, label: str) -> None:
        self.crop_canvas.set_aspect_lock(self._resolve_aspect_ratio_for_label(label))

    def _reapply_current_aspect_lock(self, preserve: str = "width") -> None:
        """Re-resolves and reapplies the currently selected aspect-combo
        option to the canvas.

        Needed in two situations that both come down to the same fix: (1)
        every commit (rotate/resize/crop/reset) resets the canvas rect to
        full bounds via set_image(), which ignores any active lock, and (2)
        "Original" must track the working image's ratio *after* a rotate,
        not the ratio at the moment "Original" was selected. Both are just
        "recompute the current label's ratio and reapply it," so this is
        the single method _sync_control_values() and _on_crop_spinbox_
        changed() both call, rather than duplicating _on_aspect_changed's
        resolution logic in either place.

        `preserve` is forwarded to CropCanvas.set_aspect_lock -- it defaults
        to "width" (the right choice for both situations above), and is
        only overridden to "height" by _on_crop_spinbox_changed when the
        user just edited the height spinbox specifically."""
        label = self.aspect_combo.currentText()
        self.crop_canvas.set_aspect_lock(self._resolve_aspect_ratio_for_label(label), preserve=preserve)

    def _apply_crop(self):
        rect = self._clamp_crop_rect(QRect(
            self.spin_crop_x.value(), self.spin_crop_y.value(),
            self.spin_crop_w.value(), self.spin_crop_h.value(),
        ))
        full_bounds = QRect(0, 0, self.working_qimage.width(), self.working_qimage.height())
        if rect == full_bounds:
            # No-op crop (e.g. the user opened the aspect combo but never
            # actually dragged/typed a smaller region) -- skip the undo
            # push and the full image copy, both wasted for a crop that
            # changes nothing.
            return

        self._push_undo_snapshot()
        transform = CropOp(rect)
        self.working_qimage = apply_transform(self.working_qimage, transform)
        self._transforms.append(transform)
        self._sync_control_values()
        self._update_info_label()

    def _reset_edits(self):
        self._push_undo_snapshot()
        self._transforms = []
        self.working_qimage = QImage(self.original_qimage)
        self._sync_control_values()
        self._update_info_label()

    def _resolve_output_format(self) -> tuple[str, str]:
        """Returns (qt_format_name, result_ext). Falls back to PNG if the
        image's original extension isn't in the Qt build's writable-formats
        list, so we never mislabel bytes with a format they aren't."""
        if self._resolved_format is not None:
            return self._resolved_format

        qt_format = _EXT_ALIASES.get(self.image_ext, self.image_ext.upper())
        supported = {bytes(fmt).decode().upper() for fmt in QImageWriter.supportedImageFormats()}
        if qt_format in supported:
            self._resolved_format = (qt_format, self.image_ext)
        else:
            self._resolved_format = ("PNG", "png")
        return self._resolved_format

    def get_result_bytes(self) -> bytes:
        qt_format, _ = self._resolve_output_format()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not self.working_qimage.save(buffer, qt_format):
            # QImage.save() returning False means the buffer holds nothing
            # usable -- without this check that would silently flow through
            # as empty bytes, which EditImageCommand would then persist as
            # the image's new (corrupt/empty) content.
            raise RuntimeError(
                f"Failed to encode the edited image as {qt_format}; refusing to "
                "return empty/partial image bytes."
            )
        return bytes(buffer.data())

    def get_result_width(self) -> int:
        return self.working_qimage.width()

    def get_result_height(self) -> int:
        return self.working_qimage.height()

    def get_result_ext(self) -> str:
        _, ext = self._resolve_output_format()
        return ext
