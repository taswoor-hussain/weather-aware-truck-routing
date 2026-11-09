"""Small geometry helpers. Coordinates are ``(lat, lon)`` tuples in degrees."""

import math
from collections.abc import Sequence

Coordinate = tuple[float, float]

EARTH_RADIUS_MILES = 3958.8
METERS_PER_MILE = 1609.344
MILES_PER_DEGREE_LAT = 69.0


def haversine_miles(a: Coordinate, b: Coordinate) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(h))


def cumulative_miles(points: Sequence[Coordinate]) -> list[float]:
    """Distance from the first point to each point along the polyline."""
    totals = [0.0]
    for previous, current in zip(points, points[1:]):
        totals.append(totals[-1] + haversine_miles(previous, current))
    return totals


def interpolate(a: Coordinate, b: Coordinate, fraction: float) -> Coordinate:
    return (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)


def simplify(points: Sequence[Coordinate], tolerance_degrees: float) -> list[Coordinate]:
    """Douglas-Peucker line simplification, iterative to avoid recursion limits."""
    if len(points) < 3:
        return list(points)

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        split, max_distance = -1, tolerance_degrees
        for index in range(start + 1, end):
            distance = _perpendicular_distance(points[index], points[start], points[end])
            if distance > max_distance:
                split, max_distance = index, distance
        if split != -1:
            keep[split] = True
            stack.append((start, split))
            stack.append((split, end))
    return [point for point, kept in zip(points, keep) if kept]


def _perpendicular_distance(point: Coordinate, start: Coordinate, end: Coordinate) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    fraction = max(0, min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared))
    return math.hypot(point[0] - (start[0] + fraction * dx), point[1] - (start[1] + fraction * dy))
