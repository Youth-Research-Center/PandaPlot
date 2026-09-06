"""
Pure representation and replay logic for ImageEditorDialog's committed edit
operations (rotate/resize/crop).

Kept separate from ImageEditorDialog so the undo-replay algorithm -- run
collapsing plus sequential application -- can be tested without any Qt
widget/dialog machinery, mirroring how crop_canvas.py's geometry helpers are
tested independently of CropCanvas's paint/mouse-event code.

ImageEditorDialog stores the *actual* sequence of committed transforms
(self._transforms) and snapshots of that list for undo/redo, rather than
decoded QImage copies -- history entries are a few dozen bytes each instead
of full images, so no cap or eviction policy is needed regardless of how
many edits a session accumulates.
"""
from dataclasses import dataclass
from typing import Union

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QTransform


@dataclass(frozen=True)
class RotateOp:
    degrees: int


@dataclass(frozen=True)
class ResizeOp:
    width: int
    height: int


@dataclass(frozen=True)
class CropOp:
    rect: QRect


Transform = Union[RotateOp, ResizeOp, CropOp]


def collapse_transforms(transforms: list[Transform]) -> list[Transform]:
    """Merges maximal consecutive runs of the same transform type:
    consecutive RotateOps collapse to one RotateOp with the summed degrees;
    consecutive ResizeOps collapse to just the last one's (width, height).
    CropOp never merges with a neighbor of any type -- it always ends
    whatever run preceded it and starts a fresh potential run after it.
    Returns a new list; never mutates `transforms`."""
    collapsed: list[Transform] = []
    for transform in transforms:
        if collapsed and isinstance(transform, RotateOp) and isinstance(collapsed[-1], RotateOp):
            collapsed[-1] = RotateOp(collapsed[-1].degrees + transform.degrees)
        elif collapsed and isinstance(transform, ResizeOp) and isinstance(collapsed[-1], ResizeOp):
            collapsed[-1] = ResizeOp(transform.width, transform.height)
        else:
            collapsed.append(transform)
    return collapsed


def apply_transform(image: QImage, transform: Transform) -> QImage:
    """Applies one transform to image, returning a new QImage. The same
    per-op logic ImageEditorDialog's commit methods (_rotate/_apply_resize/
    _apply_crop) apply directly to the live working image; this is the
    shared implementation both they and replay_transforms use."""
    if isinstance(transform, RotateOp):
        matrix = QTransform().rotate(transform.degrees)
        return image.transformed(matrix, Qt.TransformationMode.SmoothTransformation)
    if isinstance(transform, ResizeOp):
        return image.scaled(
            transform.width, transform.height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    if isinstance(transform, CropOp):
        return image.copy(transform.rect)
    raise TypeError(f"Unknown transform type: {type(transform)!r}")


def replay_transforms(original: QImage, transforms: list[Transform]) -> QImage:
    """Rebuilds the final image from `original` by collapsing consecutive
    same-type runs in `transforms` (see collapse_transforms) and applying
    the result in order. This is the only place a multi-op replay happens
    in the dialog -- used by undo, never by redo (redo applies a single
    already-known transform directly to the current image instead, via
    apply_transform)."""
    image = QImage(original)
    for transform in collapse_transforms(transforms):
        image = apply_transform(image, transform)
    return image
