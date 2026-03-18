import logging
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from django.conf import settings

from .serializers import RouteRequestSerializer, RouteResponseSerializer
from .services.geocoding import geocode_place, MapboxUnavailableError
from .services.routing import get_route, MapboxUnavailableError as RoutingUnavailableError
from .services.optimizer import optimize_fuel_stops
from django.shortcuts import render

logger = logging.getLogger(__name__)

def map_view(request):
    return render(request, 'route_map.html', {'mapbox_token': settings.MAPBOX_TOKEN})

class RouteAPIView(APIView):
    @extend_schema(
        summary='Compute optimal fuel stops for a US route',
        description='Given start and finish locations, return route geometry and a fuel stop plan.',
        request=RouteRequestSerializer,
        responses={
            200: RouteResponseSerializer,
            400: RouteResponseSerializer,
            502: RouteResponseSerializer,
            500: RouteResponseSerializer,
        },
    )
    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': 'Validation failed', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        start = serializer.validated_data['start']
        finish = serializer.validated_data['finish']

        try:
            start_coords = geocode_place(start)
            finish_coords = geocode_place(finish)
            route_data = get_route(start_coords, finish_coords)
            stops, total_cost = optimize_fuel_stops(
                route_points=route_data['geometry']['coordinates'],
                total_distance_miles=route_data['distance_miles'],
                route_stations=route_data.get('stations', None),
            )

            response = {
                'start': {'name': start, 'coordinates': [start_coords[0], start_coords[1]]},
                'finish': {'name': finish, 'coordinates': [finish_coords[0], finish_coords[1]]},
                'total_distance_miles': round(route_data['distance_miles'], 2),
                'total_fuel_gallons': round(route_data['distance_miles'] / settings.VEHICLE_MPG, 2),
                'total_fuel_cost_usd': f'{Decimal(total_cost):.2f}',
                'fuel_stops': stops,
                'route_geometry': route_data['geometry'],
            }
            out = RouteResponseSerializer(response)
            return Response(out.data)
        except (MapboxUnavailableError, RoutingUnavailableError) as exc:
            logger.error('Mapbox unavailable: %s', exc)
            return Response({'error': 'Mapbox service unreachable', 'details': {'message': [str(exc)]}}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as exc:
            return Response({'error': str(exc), 'details': {}}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception('Unexpected error in route API')
            return Response({'error': 'Internal server error', 'details': {}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
