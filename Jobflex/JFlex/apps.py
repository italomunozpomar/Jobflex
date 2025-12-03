from django.apps import AppConfig


class JflexConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'JFlex'

    def ready(self):
        import JFlex.signals # Importa el módulo de señales para registrar los receptores
