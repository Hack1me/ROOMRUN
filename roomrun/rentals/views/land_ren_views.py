from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView
from django.views.generic import FormView
from django.views.generic import ListView
from django_ratelimit.decorators import ratelimit
from djmoney.money import Money
from properties.mixins import LandlordRequiredMixin
from rentals.forms import DirectRentalContractForm
from rentals.forms import RentalContractForm
from rentals.models import RentalApplication
from rentals.models import RentalContract
from rentals.services import RentalApplicationService
from rentals.services import RentalContractService
from users.models import Tenant
from users.services import UserInvitationService
from utils.enums import ApplicationStatus
from utils.enums import UserRole


class LandlordRentalApplicationListView(LandlordRequiredMixin, ListView):
    """
    List all rental applications received by the authenticated landlord.
    """

    model = RentalApplication
    template_name = "dashboard/rentals/applications/landlord/list.html"
    context_object_name = "applications"
    paginate_by = 10

    def get_queryset(self):
        return (
            RentalApplication.landlord_objects.for_landlord(self.get_landlord())
            .select_related(
                "tenant",
                "tenant__user",
                "unit",
                "unit__building",
                "unit__building__property_ref",
            )
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status_counts = self.get_queryset().aggregate(
            total=Count("pk"),
            pending=Count("pk", filter=Q(status=ApplicationStatus.PENDING)),
            approved=Count("pk", filter=Q(status=ApplicationStatus.APPROVED)),
            rejected=Count("pk", filter=Q(status=ApplicationStatus.REJECTED)),
            cancelled=Count("pk", filter=Q(status=ApplicationStatus.CANCELLED)),
        )
        context["application_counts"] = status_counts
        return context

class LandlordRentalApplicationDetailView(LandlordRequiredMixin, DetailView):
    """
    Display a single rental application received by the authenticated landlord.
    """

    model = RentalApplication
    template_name = "dashboard/rentals/applications/landlord/detail.html"
    context_object_name = "application"

    def get_queryset(self):
        return RentalApplication.landlord_objects.for_landlord(
            self.get_landlord()
        ).select_related(
            "tenant",
            "unit",
            "unit__building",
            "unit__building__property_ref",
        )


class BaseRentalApplicationReviewView(LandlordRequiredMixin, View):
    """Base class for approving/rejecting rental applications."""

    service_method = None
    success_message = None

    def post(self, request, pk):
        application = get_object_or_404(
            RentalApplication.landlord_objects.for_landlord(self.get_landlord())
            .select_related(
                "tenant",
                "unit",
                "unit__building",
                "unit__building__property_ref",
            ),
            pk=pk,
        )

        try:
            self.service_method(application=application, reviewer=request.user)
        except ValidationError as exc:
            for message in exc.messages:
                messages.error(request, message)
            return redirect(
                "rentals:landlord-rental-application-detail",
                pk=application.pk,
            )

        messages.success(request, self.success_message)
        return redirect(
            "rentals:landlord-rental-application-detail",
            pk=application.pk,
        )


class RentalApplicationRejectView(BaseRentalApplicationReviewView):
    """Reject a rental application."""
    service_method = staticmethod(RentalApplicationService.reject)
    success_message = _("Rental application rejected successfully.")


class RentalApplicationApproveView(LandlordRequiredMixin, FormView):
    """
    Approve a rental application and create its contract
    after the landlord signs it.
    """

    form_class = RentalContractForm
    template_name = "dashboard/rentals/applications/landlord/contract_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.application = get_object_or_404(
            RentalApplication.landlord_objects.for_landlord(self.get_landlord())
            .select_related(
                "tenant",
                "tenant__user",
                "unit",
                "unit__building",
                "unit__building__property_ref",
            ),
            pk=kwargs["pk"],
        )

        has_contract = RentalContract.objects.filter(
            application=self.application
        ).exists()
        can_create_contract = (
            self.application.status == ApplicationStatus.PENDING
            or (
                self.application.status == ApplicationStatus.APPROVED
                and not has_contract
            )
        )
        if not can_create_contract:
            messages.warning(
                request, _("This application has already been reviewed.")
            )
            return redirect(
                "rentals:landlord-rental-application-detail",
                pk=self.application.pk,
            )

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["application"] = self.application
        context["tenant_user"] = self.application.tenant.user
        return context

    def get_initial(self):
        initial = super().get_initial()
        unit = self.application.unit
        start_date = self.application.desired_move_in_date
        today = timezone.localdate()

        # An application may have been submitted for a date that has since
        # passed.  A contract cannot start in the past, so default to today
        # while still allowing the landlord to choose a later date.
        if start_date and start_date < today:
            start_date = today

        initial.update({
            "start_date": start_date,
            "monthly_rent": unit.monthly_rent,
            "deposit": Money(0, unit.monthly_rent.currency),
            "advance_rent_months": 1,
        })
        return initial


    def form_valid(self, form):
        """
        Approve the application via the service, then create the
        contract in the same transaction.
        """
        try:
            with transaction.atomic():
                # Lock before deciding whether this is a new approval or a
                # retry for a previously approved application without a
                # contract (possible before the atomic fix).
                application = RentalApplication.objects.select_for_update().get(
                    pk=self.application.pk
                )
                if application.status == ApplicationStatus.PENDING:
                    application = RentalApplicationService.approve(
                        application=application,
                        reviewer=self.request.user,
                    )
                elif application.status != ApplicationStatus.APPROVED:
                    raise ValidationError(
                        _("This application can no longer create a contract.")
                    )

                # 2. Prepare contract data.
                contract_data = {
                    "start_date": form.cleaned_data["start_date"],
                    "end_date": form.cleaned_data["end_date"],
                    "monthly_rent": form.cleaned_data["monthly_rent"],
                    "deposit": form.cleaned_data["deposit"],
                    "advance_rent_months": form.cleaned_data["advance_rent_months"],
                }

                # 3. Create the contract (status = SIGNING).
                contract = RentalContractService.create(
                    tenant=application.tenant,
                    unit=application.unit,
                    application=application,
                    data=contract_data,
                    landlord_signature=form.cleaned_data["landlord_signature"],
                )
        except ValidationError as exc:
            # The exception must leave the atomic block so both the approval
            # and the attempted contract creation are rolled back together.
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)

        messages.success(
            self.request,
            _(
                "The application was approved and the rental contract "
                "is now awaiting the tenant's signature."
            ),
        )
        return redirect("rentals:landlord-rental-contract-detail", pk=contract.pk)

class LandlordRentalContractCreateView(LandlordRequiredMixin, FormView):
    """
    Create a rental contract for an existing tenant, or send an invitation
    to a new tenant (in which case the contract is deferred until acceptance).

    The tenant is selected or invited through the tenant search field.
    Contract creation is delegated to RentalContractService.
    """

    form_class = DirectRentalContractForm
    template_name = "dashboard/rentals/contracts/landlord/form.html"

    # -------------------------------------------------------------------------
    # Form setup
    # -------------------------------------------------------------------------

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["landlord"] = self.get_landlord()
        return kwargs

    # -------------------------------------------------------------------------
    # Form submission
    # -------------------------------------------------------------------------

    def form_valid(self, form):
        unit = form.cleaned_data["unit"]
        contract_data = {
            "start_date": form.cleaned_data["start_date"],
            "end_date": form.cleaned_data["end_date"],
            "monthly_rent": form.cleaned_data["monthly_rent"],
            "deposit": form.cleaned_data["deposit"],
            "advance_rent_months": form.cleaned_data["advance_rent_months"],
        }

        # -------------------------------------------------------------
        # Case 1 — Existing tenant: create the contract immediately.
        # -------------------------------------------------------------
        if not form.is_inviting():
            try:
                contract = RentalContractService.create(
                    tenant=form.get_tenant(),
                    unit=unit,
                    data=contract_data,
                    landlord_signature=form.cleaned_data["landlord_signature"],
                )
            except ValidationError as exc:
                for message in exc.messages:
                    form.add_error(None, message)
                return self.form_invalid(form)

            messages.success(
                self.request,
                _("Rental contract created successfully."),
            )
            return redirect(
                "rentals:landlord-rental-contract-detail",
                pk=contract.pk,
            )

        # -------------------------------------------------------------
        # Case 2 — New tenant: send an invitation and defer the contract.
        # -------------------------------------------------------------
        try:
            _invitation, _raw_token = UserInvitationService.create(
                email=form.get_invite_email(),
                invited_by=self.request.user,
                role=UserRole.TENANT,
            )
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)

        # The invitation workflow has no durable pending-contract model yet.
        # Do not store contract data in a browser session: it would be lost as
        # soon as the session expires and cannot be finalized reliably.
        messages.success(
            self.request,
            _(
                "The invitation was created. Create the contract after the "
                "tenant has activated their account."
            ),
        )
        return redirect("rentals:landlord-rental-contract-create")


class LandlordRentalContractListView(LandlordRequiredMixin, ListView):
    """List the authenticated landlord's rental contracts."""

    template_name = "dashboard/rentals/contracts/landlord/list.html"
    context_object_name = "contracts"
    paginate_by = 10

    def get_queryset(self):
        return (
            RentalContract.landlord_objects.for_landlord(self.get_landlord())
            .select_related("tenant__user", "unit", "unit__building")
            .order_by("-created_at")
        )


class LandlordRentalContractDetailView(LandlordRequiredMixin, DetailView):
    """Display one contract belonging to the authenticated landlord."""

    template_name = "dashboard/rentals/contracts/landlord/detail.html"
    context_object_name = "contract"

    def get_queryset(self):
        return RentalContract.landlord_objects.for_landlord(
            self.get_landlord()
        ).select_related(
            "tenant__user", "unit", "unit__building", "application"
        )


@method_decorator(
    ratelimit(key="user", rate="30/m", method="GET", block=True),
    name="dispatch",
)
class TenantSearchView(LandlordRequiredMixin, View):
    """
    Search tenants by name, email or tenant ID.

    Used by the direct rental contract form to select an existing tenant
    or to determine whether an invitation is needed.

    The endpoint is rate-limited to prevent user enumeration.
    """

    MAX_RESULTS = 10
    MIN_QUERY_LENGTH = 2

    def get(self, request, *args, **kwargs):
        query = request.GET.get("q", "").strip()

        # -------------------------------------------------------------
        # Require a minimum query length to prevent trivial enumeration.
        # -------------------------------------------------------------
        if len(query) < self.MIN_QUERY_LENGTH:
            return JsonResponse({"results": [], "can_invite": False})

        tenants = (
            Tenant.objects
            .select_related("user")
            .filter(user__is_active=True)
        )

        # -------------------------------------------------------------
        # Search by tenant ID (numeric)
        # -------------------------------------------------------------
        if query.isdigit():
            tenants = tenants.filter(pk=int(query))

        # -------------------------------------------------------------
        # Search by name or email
        # -------------------------------------------------------------
        else:
            tenants = tenants.filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(user__email__icontains=query)
            )

        tenants = tenants.order_by(
            "user__last_name",
            "user__first_name",
        )[: self.MAX_RESULTS]

        results = [
            {
                "id": tenant.pk,
                "tenant_number": tenant.tenant_number,
                "name": tenant.user.full_name,
                "email": tenant.user.email,
            }
            for tenant in tenants
        ]

        # Suggest an invitation when no result and the query looks like an email.
        can_invite = len(results) == 0 and "@" in query

        return JsonResponse({
            "results": results,
            "can_invite": can_invite,
        })
