"""Place weather checkpoints along a route at a fixed mile interval."""

from bisect import bisect_right
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .geo import Coordinate, cumulative_miles, interpolate


@dataclass(frozen=True)
class Checkpoint:
    position: Coordinate
    mile: float
    seconds_from_departure: float
    represented_miles: float


def build_checkpoints(
    points: Sequence[Coordinate],
    distance_miles: float,
    duration_seconds: float,
    interval_miles: int,
    time_profile: Sequence[tuple[int, float]] = (),
) -> list[Checkpoint]:
    """Sample a route at the origin, every ``interval_miles``, and the destination.

    Each checkpoint represents half of the stretch on either side of it, so the
    represented miles of all checkpoints add up to exactly the route length.

    ETAs come from ``time_profile`` (the routing provider's elapsed time at
    known points). Without one, elapsed time is proportional to distance.
    """
    measured = cumulative_miles(points)
    measured_total = measured[-1]
    if measured_total == 0 or distance_miles <= 0:
        raise ValueError("Route has no length.")

    # Scale to the provider's distance, which is the figure shown to the user.
    scale = distance_miles / measured_total
    miles_along = _sample_miles(distance_miles, interval_miles)
    seconds_at = _time_lookup(measured, time_profile, duration_seconds)

    checkpoints = []
    for index, mile in enumerate(miles_along):
        previous_mile = miles_along[index - 1] if index > 0 else mile
        next_mile = miles_along[index + 1] if index < len(miles_along) - 1 else mile
        checkpoints.append(
            Checkpoint(
                position=_position_at(points, measured, mile / scale),
                mile=mile,
                seconds_from_departure=seconds_at(mile / scale),
                represented_miles=(next_mile - previous_mile) / 2,
            )
        )
    return checkpoints


def _sample_miles(distance_miles: float, interval_miles: int) -> list[float]:
    count = int(distance_miles // interval_miles)
    miles = [float(step * interval_miles) for step in range(count + 1)]
    if distance_miles - miles[-1] > 0.01:
        miles.append(distance_miles)
    return miles


def _time_lookup(
    measured: Sequence[float], profile: Sequence[tuple[int, float]], duration_seconds: float
) -> Callable[[float], float]:
    """Return a function from measured miles to seconds since departure."""
    last_index = len(measured) - 1
    if len(profile) >= 2:
        known_miles = [measured[min(index, last_index)] for index, _ in profile]
        known_seconds = [seconds for _, seconds in profile]
    else:
        known_miles, known_seconds = [0.0, measured[-1]], [0.0, duration_seconds]

    def seconds_at(mile: float) -> float:
        upper = min(bisect_right(known_miles, mile), len(known_miles) - 1)
        lower = upper - 1
        span = known_miles[upper] - known_miles[lower]
        fraction = min(1.0, (mile - known_miles[lower]) / span) if span > 0 else 0.0
        return known_seconds[lower] + (known_seconds[upper] - known_seconds[lower]) * fraction

    return seconds_at


def _position_at(points: Sequence[Coordinate], measured: Sequence[float], mile: float) -> Coordinate:
    index = min(bisect_right(measured, mile), len(points) - 1)
    start, end = measured[index - 1], measured[index]
    fraction = (mile - start) / (end - start) if end > start else 0.0
    return interpolate(points[index - 1], points[index], fraction)
