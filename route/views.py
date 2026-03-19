import logging
import json
import csv
from html import escape
from decimal import Decimal

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.safestring import mark_safe
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RouteLog
from .serializers import (
    RouteLogCreateSerializer,
    RouteLogFilterSerializer,
    RouteLogSerializer,
    RouteRequestSerializer,
    RouteResponseSerializer,
)
from .services.geocoding import geocode_place, MapboxUnavailableError
from .services.optimizer import optimize_fuel_stops
from .services.routing import get_route, MapboxUnavailableError as RoutingUnavailableError

logger = logging.getLogger(__name__)


def _validate_route_request(data):
    serializer = RouteRequestSerializer(data=data)
    serializer.is_valid()
    return serializer


def _create_route_log(*, category, source, message, start='', finish='', status_code=None, details=None):
    try:
        RouteLog.objects.create(
            category=category,
            source=source,
            message=message,
            start_location=start or '',
            finish_location=finish or '',
            status_code=status_code,
            details=details or {},
        )
    except Exception:
        logger.exception('Failed to persist route log')


def _filter_route_logs(params):
    filter_serializer = RouteLogFilterSerializer(data=params)
    filter_serializer.is_valid()

    queryset = RouteLog.objects.all()
    if filter_serializer.is_valid():
        start_date = filter_serializer.validated_data.get('start_date')
        end_date = filter_serializer.validated_data.get('end_date')

        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

    return filter_serializer, queryset


def _build_route_response(start, finish):
    start_coords = geocode_place(start)
    finish_coords = geocode_place(finish)
    route_data = get_route(start_coords, finish_coords)
    stops, total_cost = optimize_fuel_stops(
        route_points=route_data['geometry']['coordinates'],
        total_distance_miles=route_data['distance_miles'],
        route_stations=route_data.get('stations', None),
    )

    return {
        'start': {'name': start, 'coordinates': [start_coords[0], start_coords[1]]},
        'finish': {'name': finish, 'coordinates': [finish_coords[0], finish_coords[1]]},
        'total_distance_miles': round(route_data['distance_miles'], 2),
        'total_fuel_gallons': round(route_data['distance_miles'] / settings.VEHICLE_MPG, 2),
        'total_fuel_cost_usd': f'{Decimal(total_cost):.2f}',
        'fuel_stops': stops,
        'route_geometry': route_data['geometry'],
    }


def _project_point(lon, lat, min_lon, min_lat, lon_span, lat_span, width, height, padding):
    inner_width = width - (padding * 2)
    inner_height = height - (padding * 2)
    x = padding + ((lon - min_lon) / lon_span) * inner_width
    y = height - padding - ((lat - min_lat) / lat_span) * inner_height
    return round(x, 1), round(y, 1)


def _build_route_svg(route_payload):
    coordinates = route_payload.get('route_geometry', {}).get('coordinates', [])
    if len(coordinates) < 2:
        return None

    width = 900
    height = 420
    padding = 30

    lons = [coord[0] for coord in coordinates]
    lats = [coord[1] for coord in coordinates]
    min_lon = min(lons)
    max_lon = max(lons)
    min_lat = min(lats)
    max_lat = max(lats)
    lon_span = max(max_lon - min_lon, 0.01)
    lat_span = max(max_lat - min_lat, 0.01)

    path_points = [
        _project_point(lon, lat, min_lon, min_lat, lon_span, lat_span, width, height, padding)
        for lon, lat in coordinates
    ]
    path_d = ' '.join(
        f'{"M" if index == 0 else "L"} {x} {y}'
        for index, (x, y) in enumerate(path_points)
    )

    start_lon, start_lat = route_payload['start']['coordinates']
    finish_lon, finish_lat = route_payload['finish']['coordinates']
    start_x, start_y = _project_point(start_lon, start_lat, min_lon, min_lat, lon_span, lat_span, width, height, padding)
    finish_x, finish_y = _project_point(finish_lon, finish_lat, min_lon, min_lat, lon_span, lat_span, width, height, padding)

    stop_markup = []
    for stop in route_payload.get('fuel_stops', []):
        stop_lon, stop_lat = stop['coordinates']
        stop_x, stop_y = _project_point(stop_lon, stop_lat, min_lon, min_lat, lon_span, lat_span, width, height, padding)
        stop_title = escape(f"{stop['station_name']} - ${stop['price_per_gallon']}/gal")
        stop_markup.append(
            f'<circle cx="{stop_x}" cy="{stop_y}" r="5" fill="#b91c1c">'
            f'<title>{stop_title}</title>'
            '</circle>'
        )

    svg = f"""
    <svg viewBox="0 0 {width} {height}" width="100%" height="320" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Route preview map">
      <rect width="{width}" height="{height}" fill="#eef6ff" rx="18" />
      <path d="{path_d}" fill="none" stroke="#f97316" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" />
      <circle cx="{start_x}" cy="{start_y}" r="8" fill="#047857" />
      <circle cx="{finish_x}" cy="{finish_y}" r="8" fill="#1d4ed8" />
      {''.join(stop_markup)}
      <text x="{padding}" y="{height - 12}" fill="#475569" font-size="16">Green = start, Blue = finish, Red = fuel stop</text>
    </svg>
    """
    return mark_safe(svg)


def map_view(request):
    start = request.GET.get('start', '').strip()
    finish = request.GET.get('finish', '').strip()
    route_payload = None
    map_error = ''
    map_error_details = {}

    if request.method == 'POST':
        if request.content_type and 'application/json' in request.content_type:
            try:
                payload = json.loads(request.body.decode('utf-8') or '{}')
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {}
            start = str(payload.get('start', start)).strip()
            finish = str(payload.get('finish', finish)).strip()
        else:
            start = request.POST.get('start', start).strip()
            finish = request.POST.get('finish', finish).strip()

    if start and finish:
        serializer = _validate_route_request({'start': start, 'finish': finish})
        if not serializer.is_valid():
            map_error = 'Validation failed'
            map_error_details = serializer.errors
            _create_route_log(
                category=RouteLog.CATEGORY_ERROR,
                source=RouteLog.SOURCE_MAP_VIEW,
                message='Validation failed',
                start=start,
                finish=finish,
                status_code=status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
            )
        else:
            start = serializer.validated_data['start']
            finish = serializer.validated_data['finish']
            try:
                route_payload = _build_route_response(start, finish)
                _create_route_log(
                    category=RouteLog.CATEGORY_SEARCH,
                    source=RouteLog.SOURCE_MAP_VIEW,
                    message='Route computed successfully',
                    start=start,
                    finish=finish,
                    status_code=status.HTTP_200_OK,
                    details={
                        'fuel_stop_count': len(route_payload.get('fuel_stops', [])),
                        'total_distance_miles': route_payload.get('total_distance_miles'),
                    },
                )
            except (MapboxUnavailableError, RoutingUnavailableError) as exc:
                logger.error('Mapbox unavailable while rendering map page: %s', exc)
                map_error = str(exc)
                _create_route_log(
                    category=RouteLog.CATEGORY_ERROR,
                    source=RouteLog.SOURCE_MAP_VIEW,
                    message='Upstream mapping service temporarily unavailable',
                    start=start,
                    finish=finish,
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    details={'message': [str(exc)]},
                )
            except ValueError as exc:
                map_error = str(exc)
                _create_route_log(
                    category=RouteLog.CATEGORY_ERROR,
                    source=RouteLog.SOURCE_MAP_VIEW,
                    message='Invalid or unsupported route',
                    start=start,
                    finish=finish,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    details={'message': [str(exc)]},
                )
            except Exception:
                logger.exception('Unexpected error in map view')
                map_error = 'Internal server error'
                _create_route_log(
                    category=RouteLog.CATEGORY_ERROR,
                    source=RouteLog.SOURCE_MAP_VIEW,
                    message='Internal server error',
                    start=start,
                    finish=finish,
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

    return render(
        request,
        'route_map.html',
        {
            'mapbox_token': settings.MAPBOX_TOKEN,
            'initial_start': start,
            'initial_finish': finish,
            'route_payload': route_payload,
            'route_payload_json': mark_safe(json.dumps(route_payload)) if route_payload else 'null',
            'route_svg': _build_route_svg(route_payload) if route_payload else None,
            'map_error': map_error,
            'map_error_details': map_error_details,
        },
    )


def health_check(request):
    return JsonResponse({'status': 'ok'})

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
        serializer = _validate_route_request(request.data)
        if not serializer.is_valid():
            _create_route_log(
                category=RouteLog.CATEGORY_ERROR,
                source=RouteLog.SOURCE_ROUTE_API,
                message='Validation failed',
                start=str(request.data.get('start', '')).strip(),
                finish=str(request.data.get('finish', '')).strip(),
                status_code=status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
            )
            return Response({'error': 'Validation failed', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        start = serializer.validated_data['start']
        finish = serializer.validated_data['finish']

        try:
            response = _build_route_response(start, finish)
            _create_route_log(
                category=RouteLog.CATEGORY_SEARCH,
                source=RouteLog.SOURCE_ROUTE_API,
                message='Route computed successfully',
                start=start,
                finish=finish,
                status_code=status.HTTP_200_OK,
                details={
                    'fuel_stop_count': len(response.get('fuel_stops', [])),
                    'total_distance_miles': response.get('total_distance_miles'),
                },
            )
            out = RouteResponseSerializer(response)
            return Response(out.data)
        except (MapboxUnavailableError, RoutingUnavailableError) as exc:
            logger.error('Mapbox unavailable: %s', exc)
            _create_route_log(
                category=RouteLog.CATEGORY_ERROR,
                source=RouteLog.SOURCE_ROUTE_API,
                message='Upstream mapping service temporarily unavailable',
                start=start,
                finish=finish,
                status_code=status.HTTP_502_BAD_GATEWAY,
                details={'message': [str(exc)]},
            )
            return Response(
                {
                    'error': 'Upstream mapping service temporarily unavailable',
                    'details': {'message': [str(exc)]},
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ValueError as exc:
            _create_route_log(
                category=RouteLog.CATEGORY_ERROR,
                source=RouteLog.SOURCE_ROUTE_API,
                message='Invalid or unsupported route',
                start=start,
                finish=finish,
                status_code=status.HTTP_400_BAD_REQUEST,
                details={'message': [str(exc)]},
            )
            return Response(
                {
                    'error': 'Invalid or unsupported route',
                    'details': {'message': [str(exc)]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception('Unexpected error in route API')
            _create_route_log(
                category=RouteLog.CATEGORY_ERROR,
                source=RouteLog.SOURCE_ROUTE_API,
                message='Internal server error',
                start=start,
                finish=finish,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            return Response({'error': 'Internal server error', 'details': {}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RouteLogCreateAPIView(APIView):
    @extend_schema(
        summary='Create a route log entry',
        description='Store a manual log entry in the database.',
        request=RouteLogCreateSerializer,
        responses={201: RouteLogSerializer, 400: RouteLogSerializer},
    )
    def post(self, request):
        serializer = RouteLogCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': 'Validation failed', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        log_entry = serializer.save()
        return Response(RouteLogSerializer(log_entry).data, status=status.HTTP_201_CREATED)


class RouteLogListAPIView(APIView):
    @extend_schema(
        summary='List route logs',
        description='Return stored logs with optional start_date and end_date filters in YYYY-MM-DD format.',
        responses={200: RouteLogSerializer(many=True), 400: RouteLogSerializer},
    )
    def get(self, request):
        filter_serializer, queryset = _filter_route_logs(request.query_params)
        download = request.query_params.get('download', '').strip().lower()
        wants_html = 'text/html' in request.META.get('HTTP_ACCEPT', '') and not download

        if wants_html:
            download_query = request.GET.copy()
            download_query.pop('download', None)
            return render(
                request._request,
                'route_logs.html',
                {
                    'logs': queryset[:200] if filter_serializer.is_valid() else [],
                    'filter_errors': filter_serializer.errors,
                    'start_date': request.GET.get('start_date', ''),
                    'end_date': request.GET.get('end_date', ''),
                    'download_query': download_query.urlencode(),
                },
            )

        if not filter_serializer.is_valid():
            return Response({'error': 'Validation failed', 'details': filter_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        serialized_logs = RouteLogSerializer(queryset, many=True).data

        if download == 'json':
            response = HttpResponse(
                json.dumps(serialized_logs, indent=2),
                content_type='application/json',
            )
            response['Content-Disposition'] = 'attachment; filename="route_logs.json"'
            return response

        if download == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="route_logs.csv"'
            writer = csv.writer(response)
            writer.writerow(['id', 'category', 'source', 'message', 'start', 'finish', 'status_code', 'details', 'created_at'])
            for item in serialized_logs:
                writer.writerow([
                    item['id'],
                    item['category'],
                    item['source'],
                    item['message'],
                    item['start'],
                    item['finish'],
                    item['status_code'],
                    json.dumps(item['details']),
                    item['created_at'],
                ])
            return response

        return Response(serialized_logs)
