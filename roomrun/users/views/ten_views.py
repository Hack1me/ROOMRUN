from django.views.generic import ListView
from properties.mixins import LandlordRequiredMixin
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
        return TenantService.get_list(
            landlord=self.get_landlord(),
            search=self.request.GET.get("q", ""),
            user_status=self.request.GET.get("status", ""),
            verified=self._get_verified_filter(),
        )

    def _get_verified_filter(self):
        """Parse the `verified` query param into True / False / None."""
        raw = self.request.GET.get("verified", "").lower()
        if raw == "true":
            return True
        if raw == "false":
            return False
        return None
