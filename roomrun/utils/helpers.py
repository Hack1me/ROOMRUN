# core/utils.py

import uuid
from typing import TypeVar

from django.db import models

M = TypeVar("M", bound=models.Model)


def generate_unique_identifier[M: models.Model](
    prefix: str, model: type[M], field: str = "id"
) -> str:
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


def assign_reference_identifier[M: models.Model](
    instance: M, *, field: str, prefix: str
) -> None:
    """Populate a model reference field when it has not yet been assigned."""
    if not getattr(instance, field):
        setattr(
            instance,
            field,
            generate_unique_identifier(
                prefix=prefix, model=type(instance), field=field
            ),
        )

def property_image_upload_path(instance, filename):
    if instance.unit_id:
        return f"properties/images/unit/{instance.unit_id}/{filename}"

    return f"properties/images/property/{instance.property_id}/{filename}"

# import os

# from django.utils.text import get_valid_filename


# def property_image_upload_path(instance, filename: str) -> str:
#     """
#     Generate the upload path for a PropertyImage.

#     - Unit images:      properties/images/unit/<unit_id>/<uuid>_<filename>
#     - Property images:  properties/images/property/<property_id>/<uuid>_<filename>

#     The UUID prefix prevents filename collisions when multiple images
#     share the same original filename.
#     """
#     # Sanitize the incoming filename
#     safe_name = get_valid_filename(filename)

#     # Generate a short unique prefix to avoid collisions
#     unique_prefix = uuid.uuid4().hex[:8]

#     # Preserve the original extension
#     _, ext = os.path.splitext(safe_name)
#     final_name = f"{unique_prefix}_{safe_name}"

#     if instance.unit_id:
#         return f"properties/images/unit/{instance.unit_id}/{final_name}"

#     if instance.property_id:
#         return f"properties/images/property/{instance.property_id}/{final_name}"

#     # Fallback (should not happen if constraints are enforced)
#     return f"properties/images/misc/{final_name}"
