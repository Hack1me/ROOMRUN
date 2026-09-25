"""Replace generated reference slugs with human-readable names."""

import re

from django.db import migrations
from django.utils.text import slugify


UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def person_name(user):
    if user is None:
        return ""
    return " ".join(
        part
        for part in (getattr(user, "first_name", ""), getattr(user, "last_name", ""))
        if part
    ).strip()


def source_name(model, obj):
    label = model._meta.label_lower
    if label == "users.user":
        return person_name(obj) or "user"
    if label in {"users.landlord", "users.tenant", "users.employee"}:
        return person_name(getattr(obj, "user", None)) or model._meta.verbose_name
    if label in {"users.maintenanceagent", "users.guard"}:
        employee = getattr(obj, "employee", None)
        return person_name(getattr(employee, "user", None)) or model._meta.verbose_name
    if label in {"rentals.rentalapplication", "rentals.rentalcontract"}:
        tenant = getattr(obj, "tenant", None)
        unit = getattr(obj, "unit", None)
        return " ".join(
            value
            for value in (
                person_name(getattr(tenant, "user", None)),
                getattr(unit, "unit_number", ""),
            )
            if value
        )
    if label == "billing.charge":
        contract = getattr(obj, "contract", None)
        tenant = getattr(contract, "tenant", None)
        unit = getattr(contract, "unit", None)
        return " ".join(
            value
            for value in (
                person_name(getattr(tenant, "user", None)),
                getattr(unit, "unit_number", ""),
                str(getattr(obj, "charge_type", "")),
            )
            if value
        )
    if label == "operations.cleaningschedule":
        building = getattr(obj, "building", None)
        return " ".join(
            value
            for value in (
                getattr(building, "name", ""),
                str(getattr(obj, "scheduled_date", "")),
            )
            if value
        )
    if label == "communications.conversationparticipant":
        return person_name(getattr(obj, "user", None)) or "conversation participant"
    if label == "communications.message":
        return getattr(obj, "content", "")[:60] or "message"
    fields = ("name", "title", "unit_number", "visitor_name", "caption")
    return next(
        (getattr(obj, name) for name in fields if getattr(obj, name, None)),
        model._meta.verbose_name,
    )


def regenerate_slugs(apps, schema_editor):
    app_label = __name__.split(".")[0]
    models_with_slugs = [
        model
        for model in apps.get_app_config(app_label).get_models()
        if any(field.name == "slug" for field in model._meta.fields)
    ]
    for model in models_with_slugs:
        model._base_manager.all().update(slug=None)

    for model in models_with_slugs:
        used = set()
        rows = model._base_manager.order_by("created_at", "pk").iterator()
        for obj in rows:
            source = UUID_PATTERN.sub("", str(source_name(model, obj)))
            base = slugify(source)[:180].strip("-") or model._meta.model_name
            slug = base
            suffix = 2
            while slug in used:
                slug = f"{base[:180]}-{suffix}"[:200]
                suffix += 1
            used.add(slug)
            obj.slug = slug[:200]
            obj.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [("rentals", "0005_human_readable_slugs")]
    operations = [migrations.RunPython(regenerate_slugs, migrations.RunPython.noop)]
