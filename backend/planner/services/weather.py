"""Hourly forecasts from Open-Meteo, batched and cached per forecast cell."""

import logging
import math
import time
from collections.abc import Collection
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import islice

import requests
from django.core.cache import cache

from .errors import UpstreamError
from .geo import Coordinate
from .risk import Weather

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_SECONDS = 30 * 60
BATCH_SIZE = 50
MAX_WORKERS = 4
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 12

# Positions snap to a forecast grid so that overlapping routes and the heatmap
# share lookups. The grid starts at 0.1 degree (about 7 miles) and widens only
# for trips so long that the lookups would threaten the API's 600-per-minute limit.
BASE_CELL_DEGREES = 0.1
MAX_CELLS_PER_PLAN = 300


@dataclass(frozen=True)
class ForecastGrid:
    cell_degrees: float = BASE_CELL_DEGREES

    def cell(self, position: Coordinate) -> Coordinate:
        size = self.cell_degrees
        return (round(round(position[0] / size) * size, 4), round(round(position[1] / size) * size, 4))


def choose_grid(positions: Collection[Coordinate]) -> ForecastGrid:
    """Return the finest grid that needs no more than ``MAX_CELLS_PER_PLAN`` lookups."""
    grid = ForecastGrid()
    while len({grid.cell(position) for position in positions}) > MAX_CELLS_PER_PLAN:
        grid = ForecastGrid(grid.cell_degrees * 2)
    return grid


@dataclass(frozen=True)
class HourlySeries:
    """Hourly values; ``start`` is the UTC time of index 0."""

    start: datetime
    wind_mph: tuple[float, ...]
    rain_in: tuple[float, ...]
    snow_in: tuple[float, ...]

    def at(self, moment: datetime) -> Weather:
        """Forecast for an exact moment.

        Wind is instantaneous, so it is interpolated between hours. Open-Meteo
        reports rain and snow as the total for the *preceding* hour, so the
        moment uses the hour that ends at or after it.
        """
        hours = (moment - self.start).total_seconds() / 3600
        last = len(self.wind_mph) - 1
        hours = max(0.0, min(float(last), hours))

        lower = math.floor(hours)
        upper = min(lower + 1, last)
        wind = self.wind_mph[lower] + (self.wind_mph[upper] - self.wind_mph[lower]) * (hours - lower)

        precipitation_index = math.ceil(hours)
        return Weather(
            wind_mph=wind,
            rain_in_hr=self.rain_in[precipitation_index],
            snow_in_hr=self.snow_in[precipitation_index],
        )


def fetch_forecasts(
    cells: set[Coordinate], window_start: datetime, window_end: datetime
) -> dict[Coordinate, HourlySeries]:
    """Return a forecast covering the window for every cell."""
    start_date = window_start.astimezone(timezone.utc).date()
    end_date = window_end.astimezone(timezone.utc).date()
    keys = {cell: _cache_key(cell, start_date, end_date) for cell in cells}

    cached = cache.get_many(list(keys.values()))
    forecasts = {cell: cached[key] for cell, key in keys.items() if key in cached}
    missing = [cell for cell in cells if cell not in forecasts]
    if not missing:
        return forecasts

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        batches = pool.map(
            lambda batch: _fetch_batch(batch, start_date, end_date),
            _chunks(missing, BATCH_SIZE),
        )
        fetched = {cell: series for batch in batches for cell, series in batch.items()}

    cache.set_many({keys[cell]: series for cell, series in fetched.items()}, CACHE_SECONDS)
    return forecasts | fetched


def _cache_key(cell: Coordinate, start_date, end_date) -> str:
    return f"weather:{cell[0]}:{cell[1]}:{start_date}:{end_date}"


def _chunks(items: list, size: int):
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


def _fetch_batch(cells: list[Coordinate], start_date, end_date) -> dict[Coordinate, HourlySeries]:
    params = {
        "latitude": ",".join(str(cell[0]) for cell in cells),
        "longitude": ",".join(str(cell[1]) for cell in cells),
        "hourly": "wind_speed_10m,rain,snowfall",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "UTC",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    payload = _request_with_retries(params)
    # Open-Meteo returns a bare object rather than a list for a single location.
    locations = payload if isinstance(payload, list) else [payload]
    return {cell: _parse_series(location) for cell, location in zip(cells, locations)}


def _request_with_retries(params: dict):
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = requests.get(FORECAST_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as error:
            logger.warning("Open-Meteo request failed: %s", error)
        else:
            if response.ok:
                return response.json()
            logger.warning("Open-Meteo returned %s: %s", response.status_code, response.text[:200])
            if response.status_code != 429 and response.status_code < 500:
                break
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(2**attempt)
    raise UpstreamError("The weather service is unavailable. Please try again in a minute.")


def _parse_series(location: dict) -> HourlySeries:
    hourly = location["hourly"]
    start = datetime.fromisoformat(hourly["time"][0]).replace(tzinfo=timezone.utc)
    return HourlySeries(
        start=start,
        wind_mph=_filled(hourly["wind_speed_10m"]),
        rain_in=_filled(hourly["rain"]),
        snow_in=_filled(hourly["snowfall"]),
    )


def _filled(values: list[float | None]) -> tuple[float, ...]:
    """Open-Meteo uses null at the far end of a model's range; treat it as calm."""
    return tuple(value if value is not None else 0.0 for value in values)
