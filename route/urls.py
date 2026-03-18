from django.urls import path

from .views import RouteAPIView, health_check, map_view

urlpatterns = [
    path('', RouteAPIView.as_view(), name='route'),
    path('map/', map_view, name='route-map'),
    path('map', map_view),
    path('health/', health_check, name='health-check'),
]
