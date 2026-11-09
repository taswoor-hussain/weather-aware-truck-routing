from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from planner.services.risk import RiskLevel, Weather, assess, heat_score
from planner.services.weather import MAX_CELLS_PER_PLAN, ForecastGrid, HourlySeries, choose_grid

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
SERIES = HourlySeries(
    start=START,
    wind_mph=(10.0, 20.0, 40.0),
    rain_in=(0.0, 0.1, 0.3),
    snow_in=(0.0, 0.0, 1.5),
)


class HourlySeriesTests(SimpleTestCase):
    def test_wind_is_interpolated_between_hours(self):
        self.assertAlmostEqual(SERIES.at(START + timedelta(minutes=30)).wind_mph, 15)

    def test_precipitation_uses_the_hour_ending_after_the_moment(self):
        weather = SERIES.at(START + timedelta(minutes=70))
        self.assertEqual(weather.rain_in_hr, 0.3)
        self.assertEqual(weather.snow_in_hr, 1.5)

    def test_moment_on_the_hour_uses_that_hours_total(self):
        self.assertEqual(SERIES.at(START + timedelta(hours=1)).rain_in_hr, 0.1)

    def test_moments_outside_the_series_are_clamped(self):
        self.assertEqual(SERIES.at(START + timedelta(hours=9)).wind_mph, 40)
        self.assertEqual(SERIES.at(START - timedelta(hours=1)).wind_mph, 10)


class ForecastGridTests(SimpleTestCase):
    def test_default_grid_rounds_to_a_tenth_of_a_degree(self):
        self.assertEqual(ForecastGrid().cell((32.7767, -96.797)), (32.8, -96.8))

    def test_short_trips_keep_the_finest_grid(self):
        positions = [(35 + i * 0.1, -100.0) for i in range(50)]
        self.assertEqual(choose_grid(positions), ForecastGrid())

    def test_long_trips_widen_the_grid_to_stay_under_the_cap(self):
        positions = [(25 + i * 0.1, -120 + i * 0.1) for i in range(1000)]
        grid = choose_grid(positions)
        self.assertGreater(grid.cell_degrees, ForecastGrid().cell_degrees)
        self.assertLessEqual(len({grid.cell(position) for position in positions}), MAX_CELLS_PER_PLAN)


class HeatScoreTests(SimpleTestCase):
    def test_tens_digit_always_matches_the_risk_level(self):
        samples = [
            Weather(wind, rain, snow)
            for wind in (0, 12, 24.9, 25, 34, 35, 44, 45, 54, 55, 70)
            for rain in (0, 0.05, 0.10, 0.25, 0.26, 0.5, 1.0, 1.2)
            for snow in (0, 0.5, 1.0, 2.0, 3.0, 3.5)
        ]
        for load in (10_000, 30_001, 40_001):
            for weather in samples:
                with self.subTest(weather=weather, load=load):
                    self.assertEqual(heat_score(weather, load) // 10, assess(weather, load).level)

    def test_shows_a_gradient_within_low(self):
        self.assertLess(heat_score(Weather(2, 0, 0), 10_000), heat_score(Weather(20, 0, 0), 10_000))

    def test_no_travel_is_the_maximum(self):
        self.assertEqual(heat_score(Weather(60, 0, 0), 10_000), int(RiskLevel.NO_TRAVEL) * 10)
