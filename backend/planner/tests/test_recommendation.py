from django.test import SimpleTestCase

from planner.services.recommendation import (
    ScoredSegment,
    explain_recommendation,
    rank_routes,
    score_route,
)
from planner.services.risk import RiskLevel


def score(duration=3600, **miles):
    levels = {
        "low": RiskLevel.LOW,
        "moderate": RiskLevel.MODERATE,
        "high": RiskLevel.HIGH,
        "severe": RiskLevel.SEVERE,
        "no_travel": RiskLevel.NO_TRAVEL,
    }
    segments = [ScoredSegment(levels[name], value) for name, value in miles.items()]
    return score_route(segments, duration)


class ScoreRouteTests(SimpleTestCase):
    def test_average_risk_is_mile_weighted(self):
        result = score(low=75, high=25)
        self.assertAlmostEqual(result.average_risk, 0.5)

    def test_empty_route_has_zero_risk(self):
        self.assertEqual(score_route([], 0).average_risk, 0)


class RankingTests(SimpleTestCase):
    def assert_first_wins(self, first, second):
        self.assertEqual(rank_routes([second, first]), [1, 0])
        self.assertEqual(rank_routes([first, second]), [0, 1])

    def test_fewest_severe_miles_comes_first(self):
        self.assert_first_wins(
            score(severe=10, high=500, duration=99_999),
            score(severe=20, low=490, duration=1),
        )

    def test_high_miles_break_severe_tie(self):
        self.assert_first_wins(
            score(severe=10, high=5, moderate=85),
            score(severe=10, high=20, low=70),
        )

    def test_average_risk_breaks_high_tie(self):
        self.assert_first_wins(
            score(high=10, low=90, duration=9_000),
            score(high=10, moderate=90, duration=1_000),
        )

    def test_travel_time_breaks_final_tie(self):
        self.assert_first_wins(score(low=100, duration=1_000), score(low=100, duration=2_000))

    def test_no_travel_is_worse_than_any_severe(self):
        self.assert_first_wins(score(severe=500), score(no_travel=1, low=499))

    def test_sampling_noise_does_not_override_lower_criteria(self):
        self.assert_first_wins(
            score(severe=10.2, low=989.8, duration=1_000),
            score(severe=10.1, low=989.9, duration=9_000),
        )


class ExplanationTests(SimpleTestCase):
    def test_names_deciding_criterion(self):
        scores = [score(high=10, low=90), score(high=30, low=70)]
        message = explain_recommendation(scores, rank_routes(scores))
        self.assertEqual(message, "Recommended for the fewest High miles.")
