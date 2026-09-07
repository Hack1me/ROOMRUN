from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import NoReverseMatch
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView
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

# Landlord dashboard view
class LandlordDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/pages/landlord.html"

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, "landlord_profile"):
            messages.error(
                request,
                _("You do not have access to the landlord dashboard.")
            )
            return redirect("dashboard:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            LandlordDashboardService.get_context(self.request.user)
        )
        return context

# Tenat Dashboard view
class TenantDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/pages/tenant.html"

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, "tenant_profile"):
            messages.error(
                request,
                _("You do not have access to the tenant dashboard.")
            )
            return redirect("dashboard:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            TenantDashboardService.get_context(self.request.user)
        )
        return context

# Maintenace Agent  Dashboard view
class MaintenanceDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/pages/maintenance.html"

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, "employee_profile") or \
           not hasattr(request.user.employee_profile, "maintenance_agent_profile"):
            messages.error(
                request,
                _("You do not have access to the maintenance dashboard.")
            )
            return redirect("dashboard:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            MaintenanceDashboardService.get_context(self.request.user)
        )
        return context

# Guard Dashboard View
class GuardDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/pages/guard.html"

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, "employee_profile") or \
           not hasattr(request.user.employee_profile, "guard_profile"):
            messages.error(
                request,
                _("You do not have access to the guard dashboard.")
            )
            return redirect("dashboard:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            GuardDashboardService.get_context(self.request.user)
        )
        return context
