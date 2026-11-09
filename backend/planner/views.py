from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import PlanRequestSerializer
from .services.errors import NoRouteError, UpstreamError
from .services.geocoding import search_places
from .services.planner import create_plan

MIN_QUERY_LENGTH = 3


class GeocodeView(APIView):
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < MIN_QUERY_LENGTH:
            return Response({"places": []})
        try:
            return Response({"places": search_places(query)})
        except UpstreamError as error:
            return Response({"detail": str(error)}, status=status.HTTP_502_BAD_GATEWAY)


class PlanView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "plan"

    def post(self, request):
        serializer = PlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(create_plan(serializer.to_plan_request()))
        except NoRouteError as error:
            return Response({"detail": str(error)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except UpstreamError as error:
            return Response({"detail": str(error)}, status=status.HTTP_502_BAD_GATEWAY)
