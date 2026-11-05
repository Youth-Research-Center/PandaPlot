"""Smooth freehand curves.

A freehand stroke is stored as the points a smooth curve passes through.
The curve is a centripetal Catmull-Rom spline (alpha = 0.5), which does not
overshoot or loop where neighbouring points are unevenly spaced, as they are
after simplification. It is drawn as cubic Bezier segments.
"""
import math

type Point = tuple[float, float]
type CubicSegment = tuple[Point, Point, Point]
"""Two control points and the end point of one cubic Bezier segment."""

_ALPHA = 0.5


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def without_repeats(points: list[Point]) -> list[Point]:
    """`points` without consecutive duplicates."""
    result: list[Point] = []
    for point in points:
        if not result or point != result[-1]:
            result.append(point)
    return result


def simplify(points: list[Point], tolerance: float) -> list[Point]:
    """Fewest of `points` that keep the stroke within `tolerance` of its
    original path (Ramer-Douglas-Peucker). The first and last points are
    always kept.

    Args:
        points: Captured stroke points.
        tolerance: Largest allowed distance from a dropped point to the
            simplified path, in the points' own units.

    Returns:
        The kept points, in order.
    """
    points = without_repeats(points)
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        farthest, farthest_distance = first, -1.0
        for index in range(first + 1, last):
            distance = _distance_to_segment(points[index], points[first], points[last])
            if distance > farthest_distance:
                farthest, farthest_distance = index, distance
        if farthest_distance > tolerance:
            keep[farthest] = True
            stack.append((first, farthest))
            stack.append((farthest, last))
    return [point for point, kept in zip(points, keep, strict=True) if kept]


def _distance_to_segment(point: Point, start: Point, end: Point) -> float:
    length = _distance(start, end)
    if length == 0.0:
        return _distance(point, start)
    # Perpendicular distance, limited to the segment's ends.
    t = ((point[0] - start[0]) * (end[0] - start[0]) + (point[1] - start[1]) * (end[1] - start[1])) / (length * length)
    t = min(max(t, 0.0), 1.0)
    closest = (start[0] + t * (end[0] - start[0]), start[1] + t * (end[1] - start[1]))
    return _distance(point, closest)


def smooth_segments(points: list[Point]) -> list[CubicSegment]:
    """Cubic Bezier segments of the smooth curve through `points`.

    The curve starts at the first point and passes through every point.
    Two points give a straight segment; fewer give no segments.
    """
    knots = without_repeats(points)
    if len(knots) < 2:
        return []
    # Reflect the ends so the first and last segments have neighbours.
    first_ghost = (2 * knots[0][0] - knots[1][0], 2 * knots[0][1] - knots[1][1])
    last_ghost = (2 * knots[-1][0] - knots[-2][0], 2 * knots[-1][1] - knots[-2][1])
    padded = [first_ghost, *knots, last_ghost]
    return [_segment(*padded[index:index + 4]) for index in range(len(knots) - 1)]


def _segment(p0: Point, p1: Point, p2: Point, p3: Point) -> CubicSegment:
    """Bezier form of the centripetal Catmull-Rom segment from p1 to p2."""
    d1 = _distance(p0, p1) ** _ALPHA
    d2 = _distance(p1, p2) ** _ALPHA
    d3 = _distance(p2, p3) ** _ALPHA
    c1 = tuple(
        (d1 * d1 * b - d2 * d2 * a + (2 * d1 * d1 + 3 * d1 * d2 + d2 * d2) * c) / (3 * d1 * (d1 + d2))
        for a, b, c in zip(p0, p2, p1, strict=True)
    )
    c2 = tuple(
        (d3 * d3 * b - d2 * d2 * a + (2 * d3 * d3 + 3 * d3 * d2 + d2 * d2) * c) / (3 * d3 * (d3 + d2))
        for a, b, c in zip(p3, p1, p2, strict=True)
    )
    return (c1[0], c1[1]), (c2[0], c2[1]), p2
