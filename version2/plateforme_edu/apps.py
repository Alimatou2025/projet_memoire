from django.apps import AppConfig


class PlateformeEduConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plateforme_edu'

    def ready(self):
        import plateforme_edu.signals  # noqa
