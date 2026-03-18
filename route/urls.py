from django.urls import path
from .views import RouteAPIView, map_view

urlpatterns = [
    path('', RouteAPIView.as_view(), name='route'),
    path('map/', map_view, name='route-map'),
]
