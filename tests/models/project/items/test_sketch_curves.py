"""Tests for freehand stroke simplification and smooth-curve segments."""
import pytest

from pandaplot.models.project.items.sketch.curves import simplify, smooth_segments, without_repeats


def _bezier(start, segment, t):
    c1, c2, end = segment
    u = 1 - t
    return tuple(u ** 3 * s + 3 * u * u * t * a + 3 * u * t * t * b + t ** 3 * e for s, a, b, e in zip(start, c1, c2, end, strict=True))


class TestSimplify:
    def test_collinear_points_reduce_to_the_ends(self):
        line = [(float(x), 2.0 * x) for x in range(20)]

        assert simplify(line, tolerance=0.1) == [(0.0, 0.0), (19.0, 38.0)]

    def test_corners_beyond_the_tolerance_are_kept(self):
        stroke = [(0.0, 0.0), (5.0, 0.1), (10.0, 0.0), (10.0, 5.0), (10.0, 10.0)]

        assert simplify(stroke, tolerance=1.0) == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]

    def test_small_wobble_within_the_tolerance_is_dropped(self):
        stroke = [(0.0, 0.0), (1.0, 0.4), (2.0, -0.4), (3.0, 0.0)]

        assert simplify(stroke, tolerance=0.5) == [(0.0, 0.0), (3.0, 0.0)]

    def test_repeated_points_are_removed_and_short_strokes_kept(self):
        assert simplify([(1.0, 1.0), (1.0, 1.0)], tolerance=1.0) == [(1.0, 1.0)]
        assert without_repeats([(0.0, 0.0), (0.0, 0.0), (1.0, 0.0), (0.0, 0.0)]) == [(0.0, 0.0), (1.0, 0.0), (0.0, 0.0)]

    def test_a_closed_loop_keeps_its_shape(self):
        loop = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]

        assert simplify(loop, tolerance=0.5) == loop


class TestSmoothSegments:
    def test_fewer_than_two_points_give_no_curve(self):
        assert smooth_segments([]) == []
        assert smooth_segments([(1.0, 1.0)]) == []

    def test_two_points_give_a_straight_segment(self):
        (c1, c2, end), = smooth_segments([(0.0, 0.0), (9.0, 0.0)])

        assert end == (9.0, 0.0)
        assert c1[1] == pytest.approx(0.0)
        assert c2[1] == pytest.approx(0.0)
        assert 0.0 < c1[0] < c2[0] < 9.0

    def test_the_curve_passes_through_every_point(self):
        knots = [(0.0, 0.0), (10.0, 5.0), (12.0, 20.0), (30.0, 18.0)]

        segments = smooth_segments(knots)

        assert [segment[2] for segment in segments] == knots[1:]
        start = knots[0]
        for segment, knot in zip(segments, knots[1:], strict=True):
            assert _bezier(start, segment, 1.0) == pytest.approx(knot)
            start = segment[2]

    def test_evenly_spaced_points_match_uniform_catmull_rom(self):
        p0, p1, p2, p3 = (0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)

        _first, middle, _last = smooth_segments([p0, p1, p2, p3])

        c1, c2, _end = middle
        assert c1 == pytest.approx((p1[0] + (p2[0] - p0[0]) / 6, 0.0))
        assert c2 == pytest.approx((p2[0] - (p3[0] - p1[0]) / 6, 0.0))

    def test_uneven_spacing_does_not_overshoot(self):
        # A long run then a tiny step: uniform Catmull-Rom would swing far
        # past the short side; the centripetal curve stays close.
        knots = [(0.0, 0.0), (100.0, 0.0), (101.0, 1.0), (101.0, 100.0)]

        segments = smooth_segments(knots)

        start = knots[0]
        for segment in segments:
            for step in range(1, 20):
                x, y = _bezier(start, segment, step / 20)
                assert -1.0 <= x <= 103.0
                assert -2.0 <= y <= 101.0
            start = segment[2]
