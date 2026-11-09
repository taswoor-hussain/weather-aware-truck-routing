"""Truck routes from the TomTom Routing API, always returning three distinct options."""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings
from django.core.cache import cache

from .errors import NoRouteError, UpstreamError
from .geo import METERS_PER_MILE, Coordinate

logger = logging.getLogger(__name__)

ROUTING_URL = "https://api.tomtom.com/routing/1/calculateRoute"
REQUEST_TIMEOUT_SECONDS = 25
CACHE_SECONDS = 10 * 60
ROUTE_COUNT = 3

KG_PER_LB = 0.45359237
# The routing engine needs gross weight, while the form asks for the load.
EMPTY_TRUCK_LB = 33_000
MAX_GROSS_LB = 80_000  # US federal limit for interstate highways.

# Detours push a via point sideways by this fraction of the trip's straight-line length.
DETOUR_OFFSETS = (0.12, -0.12, 0.22, -0.22, 0.06, -0.06)
MAX_DETOUR_RATIO = 1.6
MAX_SHARED_ROAD = 0.92
OVERLAP_GRID_DEGREES = 0.02


@dataclass(frozen=True)
class Route:
    points: tuple[Coordinate, ...]
    distance_miles: float
    duration_seconds: float
    # (index into points, seconds from departure), from the provider's traffic model.
    time_profile: tuple[tuple[int, float], ...] = ()


def fetch_routes(
    origin: Coordinate, destination: Coordinate, departure: datetime, load_lb: int
) -> list[Route]:
    places = f"{origin[0]:.5f},{origin[1]:.5f}:{destination[0]:.5f},{destination[1]:.5f}"
    key = f"routes:{places}:{departure:%Y%m%d%H%M}:{load_lb}"
    routes = cache.get(key)
    if routes is None:
        routes = _build_options(origin, destination, departure, load_lb)
        cache.set(key, routes, CACHE_SECONDS)
    return routes


def _build_options(
    origin: Coordinate, destination: Coordinate, departure: datetime, load_lb: int
) -> list[Route]:
    options = _distinct(_calculate([origin, destination], departure, load_lb, alternatives=2))
    if len(options) < ROUTE_COUNT:
        options = _add_detours(options, origin, destination, departure, load_lb)
    return options[:ROUTE_COUNT]


def _add_detours(
    options: list[Route],
    origin: Coordinate,
    destination: Coordinate,
    departure: datetime,
    load_lb: int,
) -> list[Route]:
    """TomTom may return too few alternatives, so force more through via points."""
    fastest = options[0]
    candidates = [_via_point(origin, destination, offset) for offset in DETOUR_OFFSETS]

    def attempt(via: Coordinate) -> list[Route]:
        try:
            return _calculate([origin, via, destination], departure, load_lb, alternatives=0)
        except (NoRouteError, UpstreamError):
            return []  # A via point in a lake or park is expected; try the next one.

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(attempt, candidates))

    pool_of_routes = [
        route
        for result in results
        for route in result
        if route.distance_miles <= fastest.distance_miles * MAX_DETOUR_RATIO
    ]
    return _distinct([*options, *pool_of_routes])


def _via_point(origin: Coordinate, destination: Coordinate, offset: float) -> Coordinate:
    middle_lat = (origin[0] + destination[0]) / 2
    middle_lon = (origin[1] + destination[1]) / 2
    # Rotating the trip vector 90 degrees gives the sideways direction.
    return (
        middle_lat + (destination[1] - origin[1]) * offset,
        middle_lon - (destination[0] - origin[0]) * offset,
    )


def _distinct(routes: list[Route]) -> list[Route]:
    kept: list[tuple[Route, set]] = []
    for route in routes:
        footprint = _footprint(route)
        if all(_shared_fraction(footprint, other) < MAX_SHARED_ROAD for _, other in kept):
            kept.append((route, footprint))
    return [route for route, _ in kept]


def _footprint(route: Route) -> set[tuple[int, int]]:
    return {
        (int(lat / OVERLAP_GRID_DEGREES), int(lon / OVERLAP_GRID_DEGREES))
        for lat, lon in route.points
    }


def _shared_fraction(a: set, b: set) -> float:
    return len(a & b) / min(len(a), len(b))


def _calculate(
    waypoints: list[Coordinate], departure: datetime, load_lb: int, alternatives: int
) -> list[Route]:
    locations = ":".join(f"{lat:.6f},{lon:.6f}" for lat, lon in waypoints)
    params = {
        "key": settings.TOMTOM_API_KEY,
        "travelMode": "truck",
        "vehicleCommercial": "true",
        "vehicleWeight": round(min(load_lb + EMPTY_TRUCK_LB, MAX_GROSS_LB) * KG_PER_LB),
        "routeType": "fastest",
        "traffic": "true",
        "maxAlternatives": alternatives,
        "extendedRouteRepresentation": "travelTime",
    }
    # TomTom rejects departure times that are not in the future.
    if departure > datetime.now(timezone.utc) + timedelta(minutes=1):
        params["departAt"] = departure.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        response = requests.get(
            f"{ROUTING_URL}/{locations}/json", params=params, timeout=REQUEST_TIMEOUT_SECONDS
        )
    except requests.RequestException as error:
        # Log only the type: the exception text contains the URL and its API key.
        logger.warning("TomTom request failed: %s", type(error).__name__)
        raise UpstreamError("The routing service is unavailable. Please try again.") from None

    if response.status_code == 400 and "NO_ROUTE_FOUND" in response.text:
        raise NoRouteError("No truck route was found between these locations.")
    if not response.ok:
        logger.warning("TomTom returned %s: %s", response.status_code, response.text[:300])
        raise UpstreamError("The routing service could not plan this trip. Please try again.")

    return [_parse_route(item) for item in response.json()["routes"]]


def _parse_route(item: dict) -> Route:
    points: list[Coordinate] = []
    for leg in item["legs"]:
        points.extend((point["latitude"], point["longitude"]) for point in leg["points"])
    return Route(
        points=tuple(points),
        distance_miles=item["summary"]["lengthInMeters"] / METERS_PER_MILE,
        duration_seconds=float(item["summary"]["travelTimeInSeconds"]),
        time_profile=tuple(
            (entry["pointIndex"], float(entry["travelTimeInSeconds"]))
            for entry in item.get("progress", ())
        ),
    )
