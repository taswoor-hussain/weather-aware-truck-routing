from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .services.geo import haversine_miles
from .services.planner import PlanRequest

MAX_DEPARTURE_DAYS_AHEAD = 7
DEPARTURE_GRACE_MINUTES = 15
MAX_LOAD_LB = 80_000
MIN_TRIP_MILES = 1


class PlaceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=300)
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class PlanRequestSerializer(serializers.Serializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure_at = serializers.DateTimeField()
    load_weight_lb = serializers.IntegerField(min_value=1, max_value=MAX_LOAD_LB)
    interval_miles = serializers.ChoiceField(choices=[10, 25, 50])

    def validate_departure_at(self, value):
        now = timezone.now()
        if value < now - timedelta(minutes=DEPARTURE_GRACE_MINUTES):
            raise serializers.ValidationError("Departure time cannot be in the past.")
        if value > now + timedelta(days=MAX_DEPARTURE_DAYS_AHEAD):
            raise serializers.ValidationError(
                f"Departure must be within {MAX_DEPARTURE_DAYS_AHEAD} days to use a reliable forecast."
            )
        return value

    def validate(self, attrs):
        origin = (attrs["origin"]["lat"], attrs["origin"]["lon"])
        destination = (attrs["destination"]["lat"], attrs["destination"]["lon"])
        if haversine_miles(origin, destination) < MIN_TRIP_MILES:
            raise serializers.ValidationError("Origin and destination must be different places.")
        return attrs

    def to_plan_request(self) -> PlanRequest:
        data = self.validated_data
        return PlanRequest(
            origin=(data["origin"]["lat"], data["origin"]["lon"]),
            destination=(data["destination"]["lat"], data["destination"]["lon"]),
            departure=data["departure_at"],
            load_lb=data["load_weight_lb"],
            interval_miles=data["interval_miles"],
        )
