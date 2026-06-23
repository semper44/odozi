# my_ci_project/celery.py

import os

from celery import Celery

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "odozi.settings"
)

app = Celery("odozi")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.imports = [
    'agents.tasks',
]

app.autodiscover_tasks()