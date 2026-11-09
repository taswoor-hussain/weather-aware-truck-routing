"""Orchestrates routing, weather and risk into the plan returned to the client."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from . import corridor, recommendation, routing, weather
from .checkpoints import Checkpoint, build_checkpoints
from .geo import Coordinate, simplify
from .recommendation import RouteScore, ScoredSegment
from .risk import RiskAssessment, assess, heat_score

FORECAST_SLIDER_HOURS = 48
GEOMETRY_TOLERANCE_DEGREES = 0.0005  # About 50 m: invisible on the map, far less data.
ROUTE_NAMES = ("A", "B", "C")


@dataclass(frozen=True)
class PlanRequest:
    origin: Coordinate
    destination: Coordinate
    departure: datetime
    load_lb: int
    interval_miles: int


def create_plan(request: PlanRequest) -> dict:
    routes = routing.fetch_routes(
        request.origin, request.destination, request.departure, request.load_lb
    )
    checkpoints_by_route = [
        build_checkpoints(
            route.points,
            route.distance_miles,
            route.duration_seconds,
            request.interval_miles,
            route.time_profile,
        )
        for route in routes
    ]
    grid = corridor.build_corridor([route.points for route in routes])

    heatmap_start = request.departure.replace(minute=0, second=0, microsecond=0)
    longest_hours = max(route.duration_seconds for route in routes) / 3600
    positions = [
        *grid.centers,
        *(checkpoint.position for checkpoints in checkpoints_by_route for checkpoint in checkpoints),
    ]
    forecast_grid = weather.choose_grid(positions)
    forecasts = weather.fetch_forecasts(
        {forecast_grid.cell(position) for position in positions},
        heatmap_start,
        heatmap_start + timedelta(hours=max(longest_hours, FORECAST_SLIDER_HOURS) + 2),
    )

    assessed = [
        _assess_checkpoints(checkpoints, forecasts, forecast_grid, request)
        for checkpoints in checkpoints_by_route
    ]
    scores = [
        recommendation.score_route(
            [ScoredSegment(risk.level, checkpoint.represented_miles) for checkpoint, risk, _ in items],
            route.duration_seconds,
        )
        for route, items in zip(routes, assessed)
    ]
    ranking = recommendation.rank_routes(scores)

    return {
        "routes": [
            _present_route(
                ROUTE_NAMES[index], routes[index], assessed[index], scores[index], request,
                is_recommended=index == ranking[0],
            )
            for index in ranking
        ],
        "recommendation": recommendation.explain_recommendation(scores, ranking),
        "all_routes_blocked": all(score.has_no_travel for score in scores),
        "heatmap": _present_heatmap(grid, forecasts, forecast_grid, heatmap_start, request.load_lb),
    }


def _assess_checkpoints(
    checkpoints: list[Checkpoint],
    forecasts: dict,
    forecast_grid: weather.ForecastGrid,
    request: PlanRequest,
) -> list:
    results = []
    for checkpoint in checkpoints:
        eta = request.departure + timedelta(seconds=checkpoint.seconds_from_departure)
        conditions = forecasts[forecast_grid.cell(checkpoint.position)].at(eta)
        results.append((checkpoint, assess(conditions, request.load_lb), (eta, conditions)))
    return results


def _present_route(
    name: str, route: routing.Route, items: list, score: RouteScore, request: PlanRequest,
    is_recommended: bool,
) -> dict:
    return {
        "name": name,
        "is_recommended": is_recommended,
        "distance_miles": round(route.distance_miles, 1),
        "duration_seconds": round(route.duration_seconds),
        "arrival": (request.departure + timedelta(seconds=route.duration_seconds)).isoformat(),
        "summary": {
            "low_miles": round(score.low_miles, 1),
            "moderate_miles": round(score.moderate_miles, 1),
            "high_miles": round(score.high_miles, 1),
            "severe_miles": round(score.severe_miles, 1),
            "no_travel_miles": round(score.no_travel_miles, 1),
            "average_risk": round(score.average_risk, 2),
        },
        "geometry": [
            [round(lon, 5), round(lat, 5)]
            for lat, lon in simplify(route.points, GEOMETRY_TOLERANCE_DEGREES)
        ],
        "checkpoints": [_present_checkpoint(*item) for item in items],
    }


def _present_checkpoint(checkpoint: Checkpoint, risk: RiskAssessment, forecast: tuple) -> dict:
    eta, conditions = forecast
    return {
        "lat": round(checkpoint.position[0], 5),
        "lon": round(checkpoint.position[1], 5),
        "mile": round(checkpoint.mile, 1),
        "eta": eta.isoformat(),
        "risk": int(risk.level),
        "risk_label": risk.level.label,
        "reasons": list(risk.reasons),
        "wind_mph": round(conditions.wind_mph, 1),
        "rain_in_hr": round(conditions.rain_in_hr, 2),
        "snow_in_hr": round(conditions.snow_in_hr, 2),
    }


def _present_heatmap(
    grid: corridor.CorridorGrid,
    forecasts: dict,
    forecast_grid: weather.ForecastGrid,
    start: datetime,
    load_lb: int,
) -> dict:
    moments = [start + timedelta(hours=hour) for hour in range(FORECAST_SLIDER_HOURS + 1)]
    cells = []
    for center in grid.centers:
        series = forecasts[forecast_grid.cell(center)]
        cells.append(
            {
                "lat": round(center[0], 4),
                "lon": round(center[1], 4),
                "heat": [heat_score(series.at(moment), load_lb) for moment in moments],
            }
        )
    return {"start": start.isoformat(), "cell_miles": round(grid.cell_miles, 1), "cells": cells}
