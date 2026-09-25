"""Resolve readable model slugs for views that still query by primary key."""

import re
import uuid
from contextlib import suppress

from django.apps import apps
from django.http import HttpResponsePermanentRedirect

ROUTE_MODELS = {
    "property-detail": ("properties", "Property"),
    "property-edit": ("properties", "Property"),
    "property-configure": ("properties", "Property"),
    "property-images": ("properties", "Property"),
    "property-delete": ("properties", "Property"),
    "property-image-add": ("properties", "PropertyImage"),
    "property-image-primary": ("properties", "PropertyImage"),
    "property-image-edit": ("properties", "PropertyImage"),
    "property-image-delete": ("properties", "PropertyImage"),
    "building-detail": ("properties", "Building"),
    "building-edit": ("properties", "Building"),
    "property-buildings-create": ("properties", "Property"),
    "unit-list": ("properties", "Unit"),
    "unit-create": ("properties", "Unit"),
    "unit-detail": ("properties", "Unit"),
    "unit-edit": ("properties", "Unit"),
    "unit-delete": ("properties", "Unit"),
    "unit-images": ("properties", "Unit"),
    "unit-image-add": ("properties", "PropertyImage"),
    "unit-image-primary": ("properties", "PropertyImage"),
    "unit-image-delete": ("properties", "PropertyImage"),
    "lease-document": ("rentals", "RentalContract"),
    "lease-pdf": ("rentals", "RentalContract"),
    "tenant-rental-contract-sign": ("rentals", "RentalContract"),
    "landlord-rental-contract-detail": ("rentals", "RentalContract"),
    "rental-application-detail": ("rentals", "RentalApplication"),
    "landlord-rental-application-detail": ("rentals", "RentalApplication"),
    "rental-application-approve": ("rentals", "RentalApplication"),
    "rental-application-reject": ("rentals", "RentalApplication"),
    "cleaning-detail": ("operations", "CleaningSchedule"),
    "cleaning-edit": ("operations", "CleaningSchedule"),
    "cleaning-status": ("operations", "CleaningSchedule"),
    "visitor-invitation-cancel": ("operations", "VisitorVisit"),
    "guard-visitor-status": ("operations", "VisitorVisit"),
    "notification-detail": ("communications", "Notification"),
    "notification-delete": ("communications", "Notification"),
    "notification-toggle-read": ("communications", "Notification"),
    "conversation-detail": ("communications", "Conversation"),
    "conversation-delete": ("communications", "Conversation"),
    "landlord-request-detail": ("maintenance", "MaintenanceRequest"),
    "request-detail": ("maintenance", "MaintenanceRequest"),
    "request-cancel": ("maintenance", "MaintenanceRequest"),
    "attachment-download": ("maintenance", "MaintenanceRequestAttachment"),
    "agent-claim": ("maintenance", "MaintenanceRequest"),
    "task-detail": ("maintenance", "Task"),
    "tenant-contract-payment": ("rentals", "RentalContract"),
    "tenant-payment-initiate": ("billing", "Charge"),
    "tenant-payment-sync": ("billing", "Payment"),
    "invitation-cancel": ("users", "Invitation"),
}

LEGACY_SLUG_SUFFIX = re.compile(r"^(?P<base>.+)-[0-9a-f]{8}$", re.IGNORECASE)

PARAMETER_MODELS = {
    "property_id": ("properties", "Property"),
    "building_id": ("properties", "Building"),
    "unit_id": ("properties", "Unit"),
    "image_id": ("properties", "PropertyImage"),
}


class SlugToPrimaryKeyMiddleware:
    """Keep existing UUID-based object lookups compatible with slug URLs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        url_name = getattr(request.resolver_match, "url_name", None)
        route_model = ROUTE_MODELS.get(url_name)
        view_class = getattr(view_func, "view_class", None)
        default_model = getattr(view_class, "model", None)
        queryset = getattr(view_class, "queryset", None)
        if default_model is None and queryset is not None:
            default_model = queryset.model
        if default_model is None and route_model:
            default_model = apps.get_model(*route_model)

        for name, value in tuple(view_kwargs.items()):
            model_ref = PARAMETER_MODELS.get(name)
            model = apps.get_model(*model_ref) if model_ref else None
            if name == "pk":
                model = default_model
            if model is None or not isinstance(value, str):
                continue
            try:
                view_kwargs[name] = model.objects.only("pk").get(slug=value).pk
                continue
            except model.DoesNotExist:
                legacy_match = LEGACY_SLUG_SUFFIX.fullmatch(value)
                if legacy_match:
                    current = (
                        model.objects.filter(slug=legacy_match.group("base"))
                        .only("pk", "slug")
                        .first()
                    )
                    if current:
                        canonical_path = request.path.replace(value, current.slug, 1)
                        query = request.META.get("QUERY_STRING")
                        if query:
                            canonical_path = f"{canonical_path}?{query}"
                        return HttpResponsePermanentRedirect(canonical_path)
                # Preserve old UUID links while users transition to slugs.
                with suppress(ValueError, TypeError, AttributeError):
                    view_kwargs[name] = uuid.UUID(value)
        return None
