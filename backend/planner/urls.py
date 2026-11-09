from django.urls import path

from .views import GeocodeView, PlanView

urlpatterns = [
    path("geocode/", GeocodeView.as_view()),
    path("plan/", PlanView.as_view()),
]
