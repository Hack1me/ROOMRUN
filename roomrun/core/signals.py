"""Signals shared by domain models."""

import re

from django.core.exceptions import FieldDoesNotExist
from django.db.models import CharField
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.text import slugify

UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def _person_name(user):
    if user is None:
        return ""
    return user.get_full_name().strip()


def _slug_source(sender, instance):  # noqa: C901, PLR0911
    opts = sender._meta  # noqa: SLF001
    label = opts.label_lower

    if label == "users.user":
        return _person_name(instance) or "user"
    if label in {"users.landlord", "users.tenant", "users.employee"}:
        return _person_name(getattr(instance, "user", None)) or opts.verbose_name
    if label in {"users.maintenanceagent", "users.guard"}:
        employee = getattr(instance, "employee", None)
        user = getattr(employee, "user", None)
        return _person_name(user) or opts.verbose_name
    if label in {"rentals.rentalapplication", "rentals.rentalcontract"}:
        tenant = getattr(instance, "tenant", None)
        tenant_name = _person_name(getattr(tenant, "user", None))
        unit_number = getattr(getattr(instance, "unit", None), "unit_number", "")
        return " ".join(value for value in (tenant_name, unit_number) if value)
    if label == "billing.charge":
        contract = getattr(instance, "contract", None)
        tenant = getattr(contract, "tenant", None)
        unit_number = getattr(getattr(contract, "unit", None), "unit_number", "")
        return " ".join(
            value
            for value in (
                _person_name(getattr(tenant, "user", None)),
                unit_number,
                str(getattr(instance, "charge_type", "")),
            )
            if value
        )
    if label == "operations.cleaningschedule":
        building = getattr(instance, "building", None)
        return " ".join(
            value
            for value in (
                getattr(building, "name", ""),
                str(getattr(instance, "scheduled_date", "")),
            )
            if value
        )
    if label == "communications.conversationparticipant":
        return (
            _person_name(getattr(instance, "user", None)) or "conversation participant"
        )
    if label == "communications.message":
        return getattr(instance, "content", "")[:60] or "message"

    # Only use fields intended to be names or titles. Generated reference
    # numbers, usernames, emails, tokens, and primary keys are not URL names.
    for name in ("name", "title", "unit_number", "visitor_name", "caption"):
        value = getattr(instance, name, None)
        if value:
            return value
    return opts.verbose_name


@receiver(pre_save, dispatch_uid="core.generate_model_slug")
def generate_model_slug(sender, instance, **kwargs):
    """Assign a readable slug, adding a number when a name is already used."""
    # Django's model metadata API is documented despite the leading underscore.
    opts = sender._meta  # noqa: SLF001
    try:
        slug_field = opts.get_field("slug")
    except FieldDoesNotExist:
        return
    if not isinstance(slug_field, CharField) or instance.slug:
        return

    source = UUID_PATTERN.sub("", str(_slug_source(sender, instance)))
    base = slugify(source)[:180].strip("-") or opts.model_name
    candidate = base
    suffix = 2
    existing = sender.objects.filter(slug=candidate)
    if instance.pk:
        existing = existing.exclude(pk=instance.pk)
    while existing.exists():
        candidate = f"{base[:180]}-{suffix}"[: slug_field.max_length]
        suffix += 1
        existing = sender.objects.filter(slug=candidate)
        if instance.pk:
            existing = existing.exclude(pk=instance.pk)
    instance.slug = candidate[: slug_field.max_length]
