from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("geocode/", views.geocode_suggest),
    path("plan-trip/", views.plan_trip_view),
]
