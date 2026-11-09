from django.test import SimpleTestCase

from planner.services.risk import (
    RiskLevel,
    Weather,
    assess,
    classify_rain,
    classify_snow,
    classify_wind,
)

L, M, H, S, N = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


class ThresholdTests(SimpleTestCase):
    def assert_cases(self, classify, cases):
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertIs(classify(value), expected)

    def test_wind_bands(self):
        self.assert_cases(
            classify_wind,
            [(0, L), (24.9, L), (25, M), (34.9, M), (35, H), (44.9, H),
             (45, S), (54.9, S), (55, N), (90, N)],
        )

    def test_rain_bands_are_upper_inclusive(self):
        self.assert_cases(
            classify_rain,
            [(0, L), (0.09, L), (0.10, M), (0.25, M), (0.26, H), (0.50, H),
             (0.51, S), (1.00, S), (1.01, N)],
        )

    def test_snow_bands_are_upper_inclusive(self):
        self.assert_cases(
            classify_snow,
            [(0, L), (0.49, L), (0.5, M), (1.0, M), (1.1, H), (2.0, H),
             (2.1, S), (3.0, S), (3.1, N)],
        )


class LoadRuleTests(SimpleTestCase):
    def level(self, wind, load):
        return assess(Weather(wind, 0, 0), load).level

    def test_55_mph_is_no_travel_for_any_load(self):
        self.assertIs(self.level(55, 0), N)
        self.assertIs(self.level(55, 80_000), N)

    def test_45_to_54_mph_escalates_above_30000_lb(self):
        self.assertIs(self.level(45, 30_000), S)
        self.assertIs(self.level(45, 30_001), N)
        self.assertIs(self.level(54, 30_001), N)

    def test_35_to_44_mph_escalates_above_40000_lb(self):
        self.assertIs(self.level(35, 40_000), H)
        self.assertIs(self.level(35, 40_001), S)
        self.assertIs(self.level(44, 40_001), S)

    def test_heavy_load_does_not_change_lower_wind_bands(self):
        self.assertIs(self.level(34, 80_000), M)
        self.assertIs(self.level(10, 80_000), L)


class AssessTests(SimpleTestCase):
    def test_worst_condition_wins(self):
        result = assess(Weather(wind_mph=30, rain_in_hr=0.6, snow_in_hr=0), 10_000)
        self.assertIs(result.level, S)
        self.assertEqual(result.reasons, ("Rain 0.60 in/hr",))

    def test_low_has_no_reasons(self):
        self.assertEqual(assess(Weather(5, 0, 0), 10_000).reasons, ())

    def test_escalated_wind_is_explained(self):
        result = assess(Weather(40, 0, 0), 45_000)
        self.assertEqual(result.reasons, ("Wind 40 mph with this load",))
