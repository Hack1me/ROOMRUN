"""Utilities for the ``core`` app."""

from django.urls import NoReverseMatch
from django.urls import reverse


def safe_reverse(*args, **kwargs):
    """
    ``reverse()`` wrapper that returns ``None`` when the URL cannot be resolved.

    Use this in ``get_absolute_url`` and any other model/serializer method
    that may be evaluated before the related URL patterns are wired up
    (e.g. inside the admin or DRF while the app is still being built).
    """
    try:
        return reverse(*args, **kwargs)
    except NoReverseMatch:
        return None
