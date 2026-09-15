from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from rentals.models import RentalApplication


class TenantRequiredMixin(LoginRequiredMixin):
    """Allow access only to users having a tenant profile."""

    def get_tenant(self):
        try:
            return self.request.user.tenant_profile
        except AttributeError as exc:
            raise PermissionDenied from exc


class TenantApplicationQuerysetMixin(TenantRequiredMixin):
    """
    Provides a queryset scoped to the current tenant with related
    data eagerly loaded.
    """

    def get_queryset(self):
        return (
            RentalApplication.objects
            .filter(tenant=self.get_tenant())
            .select_related(
                "unit",
                "unit__building",
                "unit__building__property_ref",
            )
        )
