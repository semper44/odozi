from django.apps import AppConfig


class GeneralConfig(AppConfig):
    name = 'general'

    def ready(self):
        from odozi.telemetry import setup_telemetry

        setup_telemetry()
