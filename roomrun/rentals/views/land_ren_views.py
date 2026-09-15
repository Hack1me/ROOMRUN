from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView
from django.views.generic import ListView
from properties.mixins import LandlordRequiredMixin
from rentals.models import RentalApplication
from rentals.services import RentalApplicationService


class LandlordRentalApplicationListView(LandlordRequiredMixin, ListView):
    """
    List all rental applications received by the authenticated landlord.
    """

    model = RentalApplication
    template_name = "dashboard/rentals/applications/landlord/list.html"
    context_object_name = "applications"
    paginate_by = 10

    def get_queryset(self):
        landlord = self.get_landlord()

        return (
            RentalApplication.objects
            .filter(unit__building__property_ref__landlord=landlord)
            .select_related(
                "tenant",
                "unit",
                "unit__building",
                "unit__building__property_ref",
            )
            .order_by("-created_at")
        )

class LandlordRentalApplicationDetailView(LandlordRequiredMixin, DetailView):
    """
    Display a single rental application received by the authenticated landlord.
    """

    model = RentalApplication
    template_name = "dashboard/rentals/applications/landlord/detail.html"
    context_object_name = "application"

    def get_queryset(self):
        landlord = self.get_landlord()

        return (
            RentalApplication.objects
            .filter(unit__building__property_ref__landlord=landlord)
            .select_related(
                "tenant",
                "unit",
                "unit__building",
                "unit__building__property_ref",
            )
        )

class BaseRentalApplicationReviewView(LandlordRequiredMixin, View):
    """Base class for approving/rejecting rental applications."""

    service_method = None

    def post(self, request, pk):
        landlord = self.get_landlord()

        application = get_object_or_404(
            RentalApplication.objects.select_related(
                "tenant",
                "unit",
                "unit__building",
                "unit__building__property_ref",
            ),
            pk=pk,
            unit__building__property_ref__landlord=landlord,
        )
        self.service_method(
            application=application,
            reviewer=request.user,
        )

        messages.success(request, self.success_message)
        return redirect(
            "rentals:landlord-rental-application-detail",
            pk=application.pk,
        )


class RentalApplicationApproveView(BaseRentalApplicationReviewView):
    service_method = staticmethod(RentalApplicationService.approve)
    success_message = _("Rental application approved successfully.")


class RentalApplicationRejectView(BaseRentalApplicationReviewView):
    service_method = staticmethod(RentalApplicationService.reject)
    success_message = _("Rental application rejected successfully.")
