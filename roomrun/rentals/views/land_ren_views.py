from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView
from django.views.generic import FormView
from django.views.generic import ListView
from properties.mixins import LandlordRequiredMixin
from rentals.forms import RentalContractForm
from rentals.models import RentalApplication
from rentals.services import RentalApplicationService
from rentals.services import RentalContractService
from utils.enums import ApplicationStatus


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

class RentalApplicationRejectView(BaseRentalApplicationReviewView):
    service_method = staticmethod(RentalApplicationService.reject)
    success_message = _("Rental application rejected successfully.")



class RentalApplicationApproveView(LandlordRequiredMixin, FormView):
    """
    Approve a rental application by creating a rental contract.

    Only accessible to the landlord who owns the unit's property.
    """

    form_class = RentalContractForm
    template_name = "dashboard/rentals/applications/landlord/contract_form.html"

    def dispatch(self, request, *args, **kwargs):
        """Pre-fetch and validate the application before handling the request."""
        self.application = get_object_or_404(
            RentalApplication.objects.select_related(
                "tenant",
                "unit",
                "unit__building",
                "unit__building__property_ref",
            ),
            pk=kwargs["pk"],
            unit__building__property_ref__landlord=self.get_landlord(),
        )

        if self.application.status != ApplicationStatus.PENDING:
            messages.warning(
                request,
                _("This application has already been reviewed."),
            )
            return redirect(
                "rentals:landlord-rental-application-detail",
                pk=self.application.pk,
            )

        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        """Pre-fill the contract form from the application data."""
        initial = super().get_initial()
        unit = self.application.unit

        initial.update({
            "start_date": self.application.desired_move_in_date,
            "monthly_rent": unit.monthly_rent.amount if unit.monthly_rent else 0,
            "deposit": 0,
            "advance_rent_months": 1,
        })

        return initial

    def form_valid(self, form):
        """Create the rental contract from a valid form."""
        try:
            contract = RentalContractService.create(
                tenant=self.application.tenant,
                unit=self.application.unit,
                application=self.application,
                reviewer=self.request.user,
                data=form.cleaned_data,
            )
        except ValidationError as e:
            # Convert service errors into form errors
            for message in e.messages:
                form.add_error(None, message)
            return self.form_invalid(form)

        messages.success(
            self.request,
            _("The rental contract has been created successfully."),
        )

        # Use the contract returned by the service, not self.application
        return redirect(
            "rentals:landlord-rental-contract-detail",
            pk=contract.pk,
        )
