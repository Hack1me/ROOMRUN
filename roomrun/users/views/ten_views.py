from django.db.models import Prefetch
from django.views.generic import ListView
from properties.mixins import LandlordRequiredMixin
from rentals.models import RentalContract
from users.models import Tenant
from users.services import TenantService


class TenantListView(LandlordRequiredMixin, ListView):
    """
    Display tenants related to the current landlord.
    """

    model = Tenant
    template_name = "dashboard/tenants/list.html"
    context_object_name = "tenants"
    paginate_by = 10

    def get_queryset(self):
        queryset = TenantService.get_list(
            landlord=self.get_landlord(),
            search=self.request.GET.get("q", ""),
            user_status=self.request.GET.get("status", ""),
            verified=self._get_verified_filter(),
        )
        return queryset.prefetch_related(
            Prefetch(
                "rental_contracts",
                queryset=RentalContract.objects.select_related(
                    "unit__building__property_ref",
                ).order_by("-created_at"),
                to_attr="listed_contracts",
            ),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "active_nav": "tenants",
                "search": self.request.GET.get("q", ""),
                "status_filter": self.request.GET.get("status", ""),
                "verified_filter": self.request.GET.get("verified", ""),
            },
        )
        return context

    def _get_verified_filter(self):
        """Parse the `verified` query param into True / False / None."""
        raw = self.request.GET.get("verified", "").lower()
        if raw == "true":
            return True
        if raw == "false":
            return False
        return None
