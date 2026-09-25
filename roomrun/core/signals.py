"""Signals shared by domain models."""

import uuid

from django.core.exceptions import FieldDoesNotExist
from django.db.models import CharField
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.text import slugify


@receiver(pre_save, dispatch_uid="core.generate_model_slug")
def generate_model_slug(sender, instance, **kwargs):
    """Create a readable, stable URL slug for every BaseModel descendant."""
    # NOTE: `Model._meta` is Django's documented metadata API despite the
    # leading underscore, so the SLF001 exemption below is intentional.
    opts = sender._meta  # noqa: SLF001
    try:
        slug_field = opts.get_field("slug")
    except FieldDoesNotExist:
        return
    if not isinstance(slug_field, CharField) or getattr(instance, "slug", None):
        return

    preferred_fields = (
        getattr(sender, "reference_field", None),
        "name",
        "title",
        "unit_number",
        "contract_number",
        "property_number",
        "visitor_name",
        "email",
        "username",
    )
    source = next(
        (
            getattr(instance, name, None)
            for name in preferred_fields
            if name and getattr(instance, name, None)
        ),
        opts.verbose_name,
    )
    base = slugify(str(source))[:180].strip("-") or opts.model_name
    suffix = uuid.uuid4().hex[:8]
    instance.slug = f"{base}-{suffix}"[: slug_field.max_length]
