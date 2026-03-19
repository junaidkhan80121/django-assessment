from rest_framework import serializers

from .models import RouteLog


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(
        max_length=200,
        allow_blank=False,
        trim_whitespace=True,
        help_text='Start location string, US place (e.g. New York, NY).',
    )
    finish = serializers.CharField(
        max_length=200,
        allow_blank=False,
        trim_whitespace=True,
        help_text='Finish location string, US place (e.g. Los Angeles, CA).',
    )

    def validate(self, attrs):
        start = attrs.get('start', '').strip()
        finish = attrs.get('finish', '').strip()
        if not start:
            raise serializers.ValidationError({'start': ['This field may not be blank.']})
        if not finish:
            raise serializers.ValidationError({'finish': ['This field may not be blank.']})
        if start.casefold() == finish.casefold():
            raise serializers.ValidationError({'finish': ['Start and finish cannot be the same location.']})

        def _looks_like_us_location(value: str) -> bool:
            # Very lightweight sanity check for "US-looking" locations:
            # requires a comma and a 2-letter state-like suffix.
            if ',' not in value:
                return False
            city, _, region = value.rpartition(',')
            region = region.strip()
            return bool(city.strip()) and len(region) == 2 and region.isalpha()

        errors = {}
        if not _looks_like_us_location(start):
            errors['start'] = ['Start should be a US city and state, e.g. "Chicago, IL".']
        if not _looks_like_us_location(finish):
            errors['finish'] = ['Finish should be a US city and state, e.g. "Denver, CO".']
        if errors:
            raise serializers.ValidationError(errors)

        return {'start': start, 'finish': finish}

class CoordinateSerializer(serializers.Serializer):
    name = serializers.CharField(help_text='Location name provided by request.')
    coordinates = serializers.ListField(
        child=serializers.FloatField(),
        min_length=2,
        max_length=2,
        help_text='Coordinates as [longitude, latitude].',
    )

class FuelStopSerializer(serializers.Serializer):
    station_name = serializers.CharField(help_text='Station name.')
    address = serializers.CharField(help_text='Station address.')
    city = serializers.CharField(help_text='Station city.')
    state = serializers.CharField(help_text='Station state.')
    coordinates = serializers.ListField(
        child=serializers.FloatField(),
        min_length=2,
        max_length=2,
        help_text='Station coordinates [longitude, latitude].',
    )
    price_per_gallon = serializers.DecimalField(max_digits=6, decimal_places=5, help_text='Fuel price per gallon.')
    miles_from_start = serializers.FloatField(help_text='Miles from start to this stop.')
    gallons_purchased = serializers.FloatField(help_text='Gallons purchased at this stop.')
    cost_at_stop = serializers.DecimalField(max_digits=10, decimal_places=2, help_text='Cost at this stop in USD.')

class RouteResponseSerializer(serializers.Serializer):
    start = CoordinateSerializer(help_text='Start location details.')
    finish = CoordinateSerializer(help_text='Finish location details.')
    total_distance_miles = serializers.FloatField(help_text='Total route distance in miles.')
    total_fuel_gallons = serializers.FloatField(help_text='Total fuel gallons for route.')
    total_fuel_cost_usd = serializers.DecimalField(max_digits=12, decimal_places=2, help_text='Total estimated fuel cost.')
    fuel_stops = FuelStopSerializer(many=True, help_text='Ordered list of recommended fuel stops.')
    route_geometry = serializers.DictField(help_text='GeoJSON route geometry object.')


class RouteLogCreateSerializer(serializers.ModelSerializer):
    start = serializers.CharField(source='start_location', required=False, allow_blank=True)
    finish = serializers.CharField(source='finish_location', required=False, allow_blank=True)

    class Meta:
        model = RouteLog
        fields = ['category', 'source', 'message', 'start', 'finish', 'status_code', 'details']


class RouteLogSerializer(serializers.ModelSerializer):
    start = serializers.CharField(source='start_location')
    finish = serializers.CharField(source='finish_location')

    class Meta:
        model = RouteLog
        fields = ['id', 'category', 'source', 'message', 'start', 'finish', 'status_code', 'details', 'created_at']


class RouteLogFilterSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)

    def validate(self, attrs):
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({'end_date': ['end_date must be on or after start_date.']})
        return attrs
