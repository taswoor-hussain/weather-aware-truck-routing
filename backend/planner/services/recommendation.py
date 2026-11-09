"""Route scoring and ranking, implementing the assessment's preference order."""

from collections.abc import Sequence
from dataclasses import dataclass

from .risk import RiskLevel


@dataclass(frozen=True)
class ScoredSegment:
    """A checkpoint's risk level and the route miles that checkpoint represents."""

    level: RiskLevel
    miles: float


@dataclass(frozen=True)
class RouteScore:
    no_travel_miles: float
    severe_miles: float
    high_miles: float
    moderate_miles: float
    low_miles: float
    average_risk: float
    duration_seconds: float

    @property
    def has_no_travel(self) -> bool:
        return self.no_travel_miles > 0

    def sort_key(self) -> tuple[float, ...]:
        """Lexicographic key: lower is better.

        The spec's order is Severe miles, High miles, average risk, travel
        time. No Travel is ranked ahead of Severe because a route the rules
        forbid can never be preferable to one they merely discourage.

        Miles and risk are rounded so that sampling noise (a fraction of a
        mile) cannot override a real difference in a lower-priority criterion.
        """
        return (
            round(self.no_travel_miles),
            round(self.severe_miles),
            round(self.high_miles),
            round(self.average_risk, 2),
            self.duration_seconds,
        )


def score_route(segments: Sequence[ScoredSegment], duration_seconds: float) -> RouteScore:
    miles_by_level = {level: 0.0 for level in RiskLevel}
    for segment in segments:
        miles_by_level[segment.level] += segment.miles

    total_miles = sum(miles_by_level.values())
    weighted = sum(level * miles for level, miles in miles_by_level.items())
    return RouteScore(
        no_travel_miles=miles_by_level[RiskLevel.NO_TRAVEL],
        severe_miles=miles_by_level[RiskLevel.SEVERE],
        high_miles=miles_by_level[RiskLevel.HIGH],
        moderate_miles=miles_by_level[RiskLevel.MODERATE],
        low_miles=miles_by_level[RiskLevel.LOW],
        average_risk=weighted / total_miles if total_miles else 0.0,
        duration_seconds=duration_seconds,
    )


def rank_routes(scores: Sequence[RouteScore]) -> list[int]:
    """Return indices into ``scores``, best route first."""
    return sorted(range(len(scores)), key=lambda index: scores[index].sort_key())


CRITERIA = (
    "the fewest No Travel miles",
    "the fewest Severe miles",
    "the fewest High miles",
    "the lowest average risk",
    "the shortest travel time",
)


def explain_recommendation(scores: Sequence[RouteScore], ranking: Sequence[int]) -> str:
    """Name the criterion that separated the winner from the runner-up."""
    if len(ranking) == 1:
        return "Only route available."

    best_key = scores[ranking[0]].sort_key()
    runner_up_key = scores[ranking[1]].sort_key()
    for description, best_value, runner_up_value in zip(CRITERIA, best_key, runner_up_key):
        if best_value != runner_up_value:
            return f"Recommended for {description}."
    return "Routes are equivalent on every criterion."
