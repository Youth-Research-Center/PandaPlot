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
    """Merges maximal consecutive runs of RotateOps into a single RotateOp
    with the summed degrees. This is safe because rotation by an exact
    multiple of 90 degrees is lossless -- QTransform.rotate() composition
    for 90/180/270-degree multiples introduces no interpolation, so
    replaying the summed rotation produces pixel-identical output to
    replaying each rotation individually.

    Consecutive ResizeOps are deliberately NOT collapsed. QImage.scaled()
    is lossy, so a run like [ResizeOp(100, 80), ResizeOp(2, 2),
    ResizeOp(100, 80)] must actually scale down to 2x2 and back up on
    replay -- collapsing it to just the final ResizeOp(100, 80) would skip
    the information loss the user's edit actually inflicted, silently
    producing a sharper/different image than what undo is supposed to
    restore. Undo/redo must reproduce the exact prior state, not a
    "cleaned up" equivalent.

    CropOp never merges with a neighbor of any type -- it always ends
    whatever run preceded it and starts a fresh potential run after it.

    This module assumes every RotateOp.degrees value is an exact multiple
    of 90. If a non-90-multiple rotation were ever introduced, the
    dimension math a following CropOp.rect relies on (captured against the
    actual working-image dimensions at the time of the crop) would diverge
    from the dimensions collapsing/replay actually produce, and
    QImage.copy() on an out-of-bounds rect pads rather than raising -- so
    such a bug would silently produce a wrong image instead of crashing.

    Returns a new list; never mutates `transforms`."""
    collapsed: list[Transform] = []
    for transform in transforms:
        if collapsed and isinstance(transform, RotateOp) and isinstance(collapsed[-1], RotateOp):
            collapsed[-1] = RotateOp(collapsed[-1].degrees + transform.degrees)
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
    rotate runs in `transforms` (see collapse_transforms) and applying the
    result in order. Used by both undo and redo in the dialog, so every
    history navigation replays from the original image rather than
    mutating the current working image in place.

    Cost note: since CropOp never collapses and ResizeOp runs are no
    longer collapsed either (see collapse_transforms), replay cost scales
    with the number of type-alternations and crops in the transform list.
    A session with many crops on a very large original image will re-run
    that many QImage.copy() passes on every undo/redo -- an accepted
    trade-off against the memory savings of storing a short list of ops
    instead of a full QImage snapshot per history entry, but one that
    could produce a visible stall in that specific scenario."""
    image = QImage(original)
    for transform in collapse_transforms(transforms):
        image = apply_transform(image, transform)
    return image
