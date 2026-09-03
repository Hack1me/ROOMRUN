import os
import sys
from pathlib import Path

from celery import Celery
from celery.signals import setup_logging

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

# Make the APPS_DIR (`roomrun/roomrun/`) importable so that the local Django
# apps (core, users, utils, ...) can be resolved when Celery boots — mirrors
# what `manage.py` does for `django-admin`.
_APPS_DIR = Path(__file__).resolve().parent.parent / "roomrun"
if _APPS_DIR.is_dir() and str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

app = Celery("roomrun")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")


@setup_logging.connect
def config_loggers(*args, **kwargs):
    from logging.config import dictConfig  # noqa: PLC0415

    from django.conf import settings  # noqa: PLC0415

    dictConfig(settings.LOGGING)


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
