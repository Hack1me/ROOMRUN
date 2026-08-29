# core/utils.py

import uuid
from typing import TypeVar

from django.db import models

M = TypeVar("M", bound=models.Model)

def generate_unique_identifier[M: models.Model](prefix: str, model: type[M], field: str = "id") -> str:  # noqa: E501
    """
    Generate a unique identifier with a given prefix and an 8-character UUID.
    The function loops until it finds an unused value, guaranteeing uniqueness.

    Args:
        prefix: The uppercase prefix (e.g., 'LND', 'TEN').
        model: The Django model class to check against.
        field: The model field name that stores the identifier (default 'id').

    Returns:
        A unique string like 'LND-A7F3B9C1'.
    """
    while True:
        identifier = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
        kwargs = {field: identifier}
        if not model.objects.filter(**kwargs).exists():
            return identifier
