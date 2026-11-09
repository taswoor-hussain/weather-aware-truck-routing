from django.test import SimpleTestCase

from planner.services.checkpoints import build_checkpoints
from planner.services.geo import haversine_miles, simplify

START = (35.0, -100.0)
END = (36.0, -100.0)


class BuildCheckpointsTests(SimpleTestCase):
    def setUp(self):
        self.distance = haversine_miles(START, END)  # about 69.1 miles
        self.duration = 3600.0

    def build(self, interval):
        return build_checkpoints([START, END], self.distance, self.duration, interval)

    def test_samples_interval_and_always_includes_destination(self):
        miles = [round(c.mile) for c in self.build(25)]
        self.assertEqual(miles, [0, 25, 50, round(self.distance)])

    def test_represented_miles_sum_to_route_length(self):
        for interval in (10, 25, 50):
            with self.subTest(interval=interval):
                total = sum(c.represented_miles for c in self.build(interval))
                self.assertAlmostEqual(total, self.distance)

    def test_eta_is_proportional_to_distance(self):
        checkpoint = self.build(25)[1]
        expected = self.duration * 25 / self.distance
        self.assertAlmostEqual(checkpoint.seconds_from_departure, expected)

    def test_positions_lie_along_route(self):
        last = self.build(25)[-1]
        self.assertAlmostEqual(last.position[0], END[0])

    def test_route_shorter_than_interval_has_both_ends(self):
        checkpoints = build_checkpoints([START, END], self.distance, self.duration, 50)
        short = build_checkpoints([START, (35.1, -100.0)], 6.9, 600, 50)
        self.assertEqual(len(short), 2)
        self.assertEqual(len(checkpoints), 3)


class SimplifyTests(SimpleTestCase):
    def test_removes_collinear_points_and_keeps_corners(self):
        line = [(0, 0), (1, 0.00001), (2, 0), (2, 2)]
        self.assertEqual(simplify(line, 0.001), [(0, 0), (2, 0), (2, 2)])


class TimeProfileTests(SimpleTestCase):
    def test_eta_follows_the_providers_time_profile(self):
        points = [(35.0, -100.0), (35.5, -100.0), (36.0, -100.0)]
        distance = haversine_miles(points[0], points[2])
        # The first half of the route takes 3000 s and the second half 1000 s.
        profile = [(0, 0.0), (1, 3000.0), (2, 4000.0)]
        checkpoints = build_checkpoints(points, distance, 4000.0, 10, profile)
        by_mile = {round(c.mile): c.seconds_from_departure for c in checkpoints}
        expected = 3000 * 20 / haversine_miles(points[0], points[1])
        self.assertAlmostEqual(by_mile[20], expected)
        self.assertAlmostEqual(checkpoints[-1].seconds_from_departure, 4000.0, delta=1)
