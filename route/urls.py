from django.urls import path

from .views import RouteAPIView, RouteLogCreateAPIView, RouteLogListAPIView, health_check, map_view

urlpatterns = [
    path('', RouteAPIView.as_view(), name='route'),
    path('logs/', RouteLogListAPIView.as_view(), name='route-logs-list'),
    path('logs/create/', RouteLogCreateAPIView.as_view(), name='route-logs-create'),
    path('map/', map_view, name='route-map'),
    path('map', map_view),
    path('health/', health_check, name='health-check'),
]
