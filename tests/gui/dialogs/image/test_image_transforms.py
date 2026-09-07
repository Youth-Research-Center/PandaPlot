import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.image.image_transforms import (
    CropOp,
    ResizeOp,
    RotateOp,
    apply_transform,
    collapse_transforms,
    replay_transforms,
)


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _blank_image(width: int, height: int) -> QImage:
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(0x00FF00)
    return img


def _quadrant_image(size: int = 40) -> QImage:
    """A size x size image with each quadrant a distinct solid color:
    top-left=red, top-right=green, bottom-left=blue, bottom-right=yellow.
    A solid-color fixture can't distinguish a correct crop/rotation from
    one with a swapped origin or reversed direction, since dimension and
    uniform-pixel checks pass either way -- this fixture lets tests assert
    on which quadrant actually ends up where."""
    half = size // 2
    img = QImage(size, size, QImage.Format.Format_RGB32)
    img.fill(QColor("black"))
    for x in range(half):
        for y in range(half):
            img.setPixelColor(x, y, QColor("red"))
            img.setPixelColor(half + x, y, QColor("green"))
            img.setPixelColor(x, half + y, QColor("blue"))
            img.setPixelColor(half + x, half + y, QColor("yellow"))
    return img


class TestCollapseTransforms:
    def test_single_element_list_is_unchanged(self):
        transforms = [RotateOp(90)]
        assert collapse_transforms(transforms) == [RotateOp(90)]

    def test_consecutive_rotates_sum_their_degrees(self):
        transforms = [RotateOp(90), RotateOp(90), RotateOp(-90)]
        assert collapse_transforms(transforms) == [RotateOp(90)]

    def test_consecutive_resizes_are_not_collapsed(self):
        # Resize runs are deliberately left uncollapsed -- QImage.scaled()
        # is lossy, so undo must be able to replay the actual down-then-up
        # scaling round-trip rather than silently skipping the information
        # loss it caused (see collapse_transforms's docstring).
        transforms = [ResizeOp(50, 50), ResizeOp(200, 100), ResizeOp(10, 10)]
        assert collapse_transforms(transforms) == [
            ResizeOp(50, 50), ResizeOp(200, 100), ResizeOp(10, 10),
        ]

    def test_crop_interrupts_a_run_producing_two_segments(self):
        transforms = [
            RotateOp(90), RotateOp(90),
            CropOp(QRect(0, 0, 10, 10)),
            RotateOp(-90), RotateOp(-90),
        ]
        assert collapse_transforms(transforms) == [
            RotateOp(180),
            CropOp(QRect(0, 0, 10, 10)),
            RotateOp(-180),
        ]

    def test_crop_interrupts_a_resize_run_leaving_both_segments_uncollapsed(self):
        transforms = [
            ResizeOp(50, 50), ResizeOp(10, 10),
            CropOp(QRect(0, 0, 5, 5)),
            ResizeOp(20, 20), ResizeOp(15, 15),
        ]
        assert collapse_transforms(transforms) == transforms

    def test_alternating_types_are_not_merged(self):
        transforms = [RotateOp(90), ResizeOp(50, 50), RotateOp(-90)]
        assert collapse_transforms(transforms) == [
            RotateOp(90), ResizeOp(50, 50), RotateOp(-90),
        ]

    def test_empty_list_stays_empty(self):
        assert collapse_transforms([]) == []


class TestApplyTransform:
    def test_rotate_90_swaps_dimensions(self):
        image = _blank_image(100, 80)
        result = apply_transform(image, RotateOp(90))
        assert result.width() == 80
        assert result.height() == 100

    def test_rotate_90_clockwise_moves_each_quadrant_to_the_correct_corner(self):
        # RotateOp(90) is what the dialog's "clockwise" button
        # (self._rotate(90)) applies. A dimension-only check can't tell a
        # correct clockwise rotation from an accidentally-reversed one, so
        # this asserts on which quadrant actually ends up where: rotating
        # a square 90 degrees clockwise moves the old bottom-left corner
        # to the new top-left, old top-left to new top-right, old
        # top-right to new bottom-right, and old bottom-right to new
        # bottom-left.
        image = _quadrant_image(40)
        result = apply_transform(image, RotateOp(90))

        assert result.pixelColor(5, 5) == QColor("blue")      # was bottom-left
        assert result.pixelColor(34, 5) == QColor("red")      # was top-left
        assert result.pixelColor(5, 34) == QColor("yellow")   # was bottom-right
        assert result.pixelColor(34, 34) == QColor("green")   # was top-right

    def test_rotate_negative_90_counterclockwise_moves_each_quadrant_to_the_correct_corner(self):
        # RotateOp(-90) is what the dialog's "counterclockwise" button
        # (self._rotate(-90)) applies -- the mirror image of the clockwise
        # case above.
        image = _quadrant_image(40)
        result = apply_transform(image, RotateOp(-90))

        assert result.pixelColor(5, 5) == QColor("green")     # was top-right
        assert result.pixelColor(34, 5) == QColor("yellow")   # was bottom-right
        assert result.pixelColor(5, 34) == QColor("red")      # was top-left
        assert result.pixelColor(34, 34) == QColor("blue")    # was bottom-left

    def test_resize_sets_exact_target_dimensions(self):
        image = _blank_image(100, 80)
        result = apply_transform(image, ResizeOp(40, 30))
        assert result.width() == 40
        assert result.height() == 30

    def test_crop_produces_exact_rect_dimensions(self):
        image = _blank_image(100, 80)
        result = apply_transform(image, CropOp(QRect(10, 10, 40, 30)))
        assert result.width() == 40
        assert result.height() == 30

    def test_crop_extracts_the_correct_region_not_just_the_correct_size(self):
        # A crop rect positioned at the wrong origin (e.g. x/y swapped, or
        # measured from the wrong corner) would still produce the right
        # *dimensions* -- only checking the extracted pixels' content can
        # tell the difference. QRect(20, 20, 20, 20) on the 40x40 quadrant
        # image should extract exactly the bottom-right (yellow) quadrant.
        image = _quadrant_image(40)
        result = apply_transform(image, CropOp(QRect(20, 20, 20, 20)))

        assert result.width() == 20
        assert result.height() == 20
        for x in range(20):
            for y in range(20):
                assert result.pixelColor(x, y) == QColor("yellow")


class TestReplayTransforms:
    def test_empty_transform_list_returns_a_copy_of_the_original(self):
        original = _blank_image(100, 80)
        result = replay_transforms(original, [])
        assert result.width() == 100
        assert result.height() == 80
        assert result is not original  # a fresh copy, not the same object

    def test_replaying_a_mixed_sequence_matches_manual_sequential_application(self):
        original = _blank_image(200, 100)
        transforms = [
            RotateOp(90), RotateOp(90),  # collapses to RotateOp(180): 200x100 -> 200x100
            ResizeOp(120, 60),
            CropOp(QRect(10, 10, 40, 30)),
            RotateOp(-90),
        ]
        replayed = replay_transforms(original, transforms)

        # Manually apply the same (uncollapsed) sequence step by step and
        # confirm the result is pixel-identical, not just same-sized --
        # collapsing must never change the final result at all, only how
        # many passes it takes to get there. This holds because the only
        # collapsing that happens here is the rotate run (90+90 -> 180),
        # which is lossless for exact 90-degree multiples; resizes are
        # never collapsed, so both paths apply the identical resize/crop
        # operations in the identical order.
        manual = QImage(original)
        for t in transforms:
            manual = apply_transform(manual, t)

        assert replayed == manual

    def test_does_not_mutate_the_original_image(self):
        original = _blank_image(100, 80)
        replay_transforms(original, [RotateOp(90), ResizeOp(10, 10)])
        assert original.width() == 100
        assert original.height() == 80
