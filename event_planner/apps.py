import os
from django.apps import AppConfig



class EventPlannerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'event_planner'

    def ready(self):
        import event_planner.signals
        from . import scheduler

