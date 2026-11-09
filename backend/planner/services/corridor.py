"""Build the grid of heatmap cells that covers the corridor around all routes."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .geo import MILES_PER_DEGREE_LAT, Coordinate, cumulative_miles, haversine_miles

BUFFER_MILES = 30
MIN_CELL_MILES = 10
MAX_CELLS = 170
GROWTH_FACTOR = 1.15


@dataclass(frozen=True)
class CorridorGrid:
    centers: list[Coordinate]
    cell_miles: float


def build_corridor(routes: Sequence[Sequence[Coordinate]]) -> CorridorGrid:
    """Choose the finest grid that stays under ``MAX_CELLS``.

    Each cell is one weather lookup, so the cap bounds API usage however long
    the trip is.
    """
    mean_lat = sum(route[0][0] for route in routes) / len(routes)
    cell_miles = float(MIN_CELL_MILES)
    while True:
        centers = _cells_near_routes(routes, cell_miles, mean_lat)
        if len(centers) <= MAX_CELLS:
            return CorridorGrid(centers, cell_miles)
        cell_miles *= GROWTH_FACTOR


def _cells_near_routes(
    routes: Sequence[Sequence[Coordinate]], cell_miles: float, mean_lat: float
) -> list[Coordinate]:
    lat_step = cell_miles / MILES_PER_DEGREE_LAT
    lon_step = lat_step / math.cos(math.radians(mean_lat))
    reach = math.ceil(BUFFER_MILES / cell_miles)

    centers: dict[tuple[int, int], Coordinate] = {}
    for route in routes:
        for anchor in _thin(route, cell_miles / 2):
            row, column = round(anchor[0] / lat_step), round(anchor[1] / lon_step)
            for row_offset in range(-reach, reach + 1):
                for column_offset in range(-reach, reach + 1):
                    index = (row + row_offset, column + column_offset)
                    if index in centers:
                        continue
                    center = (index[0] * lat_step, index[1] * lon_step)
                    if haversine_miles(anchor, center) <= BUFFER_MILES:
                        centers[index] = center
    return list(centers.values())


def _thin(points: Sequence[Coordinate], spacing_miles: float) -> list[Coordinate]:
    """Keep the first point at or beyond each multiple of the spacing."""
    kept = []
    next_mile = 0.0
    for point, mile in zip(points, cumulative_miles(points)):
        if mile >= next_mile:
            kept.append(point)
            next_mile = mile + spacing_miles
    return kept
