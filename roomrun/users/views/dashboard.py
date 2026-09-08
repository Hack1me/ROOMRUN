from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import NoReverseMatch
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView
from users.mixins import DashboardProfileMixin
from users.services import DashboardService
from users.services import GuardDashboardService
from users.services import LandlordDashboardService
from users.services import MaintenanceDashboardService
from users.services import TenantDashboardService


class DashboardView(LoginRequiredMixin, View):
    """
    Entry point for the dashboard.

    Redirects the user to the appropriate dashboard based on their role.
    The role is determined by the DashboardService.
    """

    # URL name for the fallback dashboard (if role is unknown)
    FALLBACK_ROLE = "user"

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests - redirect to the user's dashboard.
        """
        dashboard = DashboardService.get_dashboard(request.user)
        role = dashboard.role

        # Attempt to resolve the URL for the given role
        try:
            url = reverse(f"dashboard:{role}")
        except NoReverseMatch:
            # Log the error (optional) and fallback to a default role
            # In production, use logging.error()
            messages.warning(
                request,
                _("Your dashboard is being prepared. Redirecting to the main dashboard.")  # noqa: E501
            )
            url = reverse(f"dashboard:{self.FALLBACK_ROLE}")

        return redirect(url)

class LandlordDashboardView(LoginRequiredMixin, DashboardProfileMixin, TemplateView):
    template_name = "dashboard/pages/landlord.html"
    profile_attr = "landlord_profile"
    error_message = _("You do not have access to the landlord dashboard.")
    service_class = LandlordDashboardService


class TenantDashboardView(LoginRequiredMixin, DashboardProfileMixin, TemplateView):
    template_name = "dashboard/pages/tenant.html"
    profile_attr = "tenant_profile"
    error_message = _("You do not have access to the tenant dashboard.")
    service_class = TenantDashboardService


class MaintenanceDashboardView(LoginRequiredMixin, DashboardProfileMixin, TemplateView):
    template_name = "dashboard/pages/maintenance.html"
    profile_attr = "employee_profile.maintenance_agent_profile"
    error_message = _("You do not have access to the maintenance dashboard.")
    service_class = MaintenanceDashboardService


class GuardDashboardView(LoginRequiredMixin, DashboardProfileMixin, TemplateView):
    template_name = "dashboard/pages/guard.html"
    profile_attr = "employee_profile.guard_profile"
    error_message = _("You do not have access to the guard dashboard.")
    service_class = GuardDashboardService
