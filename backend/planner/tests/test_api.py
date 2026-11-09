from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from planner.services.errors import NoRouteError
from planner.services.geocoding import _to_place, _unique
from planner.services.routing import Route, _distinct, _parse_route


def valid_payload(**overrides):
    return {
        "origin": {"label": "Dallas", "lat": 32.78, "lon": -96.8},
        "destination": {"label": "Chicago", "lat": 41.88, "lon": -87.63},
        "departure_at": (timezone.now() + timedelta(hours=1)).isoformat(),
        "load_weight_lb": 35_000,
        "interval_miles": 25,
    } | overrides


class PlanEndpointTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def post(self, payload):
        return self.client.post("/api/plan/", payload, format="json")

    def test_rejects_invalid_interval(self):
        self.assertEqual(self.post(valid_payload(interval_miles=30)).status_code, 400)

    def test_rejects_past_departure(self):
        past = (timezone.now() - timedelta(hours=2)).isoformat()
        response = self.post(valid_payload(departure_at=past))
        self.assertEqual(response.status_code, 400)
        self.assertIn("departure_at", response.json())

    def test_rejects_missing_load(self):
        payload = valid_payload()
        del payload["load_weight_lb"]
        self.assertEqual(self.post(payload).status_code, 400)

    def test_rejects_identical_places(self):
        same = {"label": "Dallas", "lat": 32.78, "lon": -96.8}
        self.assertEqual(self.post(valid_payload(origin=same, destination=same)).status_code, 400)

    def test_reports_no_route(self):
        with mock.patch("planner.views.create_plan", side_effect=NoRouteError("No truck route.")):
            response = self.post(valid_payload())
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "No truck route.")


class RouteParsingTests(SimpleTestCase):
    def test_parses_points_summary_and_time_profile(self):
        route = _parse_route(
            {
                "summary": {"lengthInMeters": 1609.344, "travelTimeInSeconds": 60},
                "legs": [{"points": [{"latitude": 1, "longitude": 2}, {"latitude": 3, "longitude": 4}]}],
                "progress": [{"pointIndex": 0, "travelTimeInSeconds": 0}, {"pointIndex": 1, "travelTimeInSeconds": 60}],
            }
        )
        self.assertEqual(route.points, ((1, 2), (3, 4)))
        self.assertAlmostEqual(route.distance_miles, 1)
        self.assertEqual(route.time_profile, ((0, 0.0), (1, 60.0)))

    def test_near_identical_routes_are_dropped(self):
        points = tuple((35 + i * 0.05, -100.0) for i in range(50))
        different = tuple((35 + i * 0.05, -101.0) for i in range(50))
        routes = [Route(points, 100, 100), Route(points, 101, 101), Route(different, 120, 120)]
        self.assertEqual(len(_distinct(routes)), 2)


class GeocodingTests(SimpleTestCase):
    def test_labels_points_of_interest_with_their_name(self):
        place = _to_place(
            {
                "address": {"freeformAddress": "1 Main St, Dallas, TX"},
                "poi": {"name": "Truck Depot"},
                "position": {"lat": 32.7, "lon": -96.8},
            }
        )
        self.assertEqual(place, {"label": "Truck Depot, 1 Main St, Dallas, TX", "lat": 32.7, "lon": -96.8})

    def test_duplicate_labels_keep_the_best_ranked_result(self):
        first, second = {"label": "Dallas, TX", "lat": 1, "lon": 1}, {"label": "Dallas, TX", "lat": 2, "lon": 2}
        self.assertEqual(_unique([first, second]), [first])
