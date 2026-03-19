from django.db import models


class RouteLog(models.Model):
    CATEGORY_SEARCH = 'search'
    CATEGORY_ERROR = 'error'
    CATEGORY_INFO = 'info'
    CATEGORY_CHOICES = [
        (CATEGORY_SEARCH, 'Search'),
        (CATEGORY_ERROR, 'Error'),
        (CATEGORY_INFO, 'Info'),
    ]

    SOURCE_ROUTE_API = 'route_api'
    SOURCE_MAP_VIEW = 'map_view'
    SOURCE_MANUAL = 'manual'
    SOURCE_CHOICES = [
        (SOURCE_ROUTE_API, 'Route API'),
        (SOURCE_MAP_VIEW, 'Map View'),
        (SOURCE_MANUAL, 'Manual'),
    ]

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    message = models.CharField(max_length=255)
    start_location = models.CharField(max_length=200, blank=True)
    finish_location = models.CharField(max_length=200, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.category} [{self.source}] {self.message}'
