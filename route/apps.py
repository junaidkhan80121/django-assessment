import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)

class RouteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'route'

    def ready(self):
        try:
            from .services import fuel_loader
            fuel_loader.load_fuel_data()
        except Exception as exc:
            logger.warning('Fuel loader failed during startup: %s', exc)
