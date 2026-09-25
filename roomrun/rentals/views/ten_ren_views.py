from billing.models import Charge
from communications.services.notification_ser import send_notification
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import FormView
from django.views.generic import ListView
from rentals.forms import ContractExtensionRequestForm
from rentals.forms import RentalApplicationForm
from rentals.forms import TenantContractSignatureForm
from rentals.mixins import TenantApplicationQuerysetMixin
from rentals.mixins import TenantRequiredMixin
from rentals.models import RentalApplication
from rentals.models import RentalContract
from rentals.services import ContractExtensionService
from rentals.services import RentalApplicationService
from rentals.services import RentalContractService
from utils.enums import ContractStatus
from utils.enums import NotificationType
from utils.enums import PaymentMethod


class RentalApplicationListView(TenantApplicationQuerysetMixin, ListView):
    template_name = "dashboard/rentals/applications/list.html"
    context_object_name = "applications"
    paginate_by = 10


class RentalApplicationDetailView(TenantApplicationQuerysetMixin, DetailView):
    template_name = "dashboard/rentals/applications/detail.html"
    context_object_name = "application"


class RentalApplicationCreateView(TenantRequiredMixin, CreateView):
    model = RentalApplication
    form_class = RentalApplicationForm
    template_name = "dashboard/rentals/applications/form.html"

    def get_form_kwargs(self):
        """
        Pass the tenant to the form so it can filter units and prevent
        duplicate pending applications.
        """
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.get_tenant()
        return kwargs

    def form_valid(self, form):
        tenant = self.get_tenant()

        try:
            RentalApplicationService.create(
                tenant=tenant,
                data=form.cleaned_data,
            )
        except Exception as exc:  # noqa: BLE001
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        messages.success(
            self.request,
            _("Your rental application has been submitted successfully."),
        )

        return redirect("rentals:rental-application-list")


class TenantRentalContractSignView(TenantRequiredMixin, FormView):
    """Allow the contract's tenant to sign a contract awaiting signature."""

    form_class = TenantContractSignatureForm
    template_name = "dashboard/rentals/contracts/tenant/sign.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        self.contract = get_object_or_404(
            RentalContract.objects.select_related("unit", "unit__building"),
            pk=kwargs["pk"],
            tenant=self.get_tenant(),
            status=ContractStatus.SIGNING,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["contract"] = self.contract
        return context

    def form_valid(self, form):
        try:
            RentalContractService.sign_by_tenant(
                contract=self.contract,
                tenant_signature=form.cleaned_data["tenant_signature"],
            )
            RentalContractService.create_initial_payment(
                contract=self.contract,
                payment_method=PaymentMethod.MOBILE_MONEY,
            )
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
            return self.form_invalid(form)

        messages.success(self.request, _("Rental contract signed successfully."))
        return redirect("billing:tenant-charge-list")


class TenantLeaseDetailView(LoginRequiredMixin, DetailView):
    """
    Display the authenticated tenant's current rental contract.

    If the tenant has multiple contracts, the ACTIVE one takes priority,
    then SIGNED, then SIGNING.
    """

    template_name = "dashboard/rentals/leases/tenant/detail.html"
    context_object_name = "contract"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = context["contract"]
        initial_charge = contract.charges.filter(charge_type="INITIAL_PAYMENT").first()
        if initial_charge:
            context["initial_payment_due"] = initial_charge.balance_due
        else:
            context["initial_payment_due"] = (
                RentalContractService.calculate_initial_payment(contract=contract)
            )
        extensions = list(contract.extension_requests.all())
        charges = {
            charge.pk: charge
            for charge in Charge.objects.filter(
                pk__in=[
                    item.payment_charge_id
                    for item in extensions
                    if item.payment_charge_id
                ]
            )
        }
        for extension in extensions:
            extension.payment_charge = charges.get(extension.payment_charge_id)
        context["extension_requests"] = extensions
        return context

    def get_queryset(self):
        return (
            RentalContract.objects
            .filter(
                tenant__user=self.request.user,
                status__in=[
                    ContractStatus.SIGNING,
                    ContractStatus.SIGNED,
                    ContractStatus.ACTIVE,
                    ContractStatus.TERMINATED,
                ],
            )
            .select_related(
                "tenant",
                "tenant__user",
                "unit",
                "unit__building",
                "unit__building__property_ref",
                "unit__building__property_ref__landlord",
            )
        )

    def get_object(self, queryset=None):
        """
        Return the most relevant contract.

        Priority: ACTIVE > SIGNED > SIGNING.
        """
        if queryset is None:
            queryset = self.get_queryset()

        # Define the priority order.
        priority = {
            ContractStatus.ACTIVE: 0,
            ContractStatus.SIGNED: 1,
            ContractStatus.SIGNING: 2,
            ContractStatus.TERMINATED: 3,
        }

        contracts = list(queryset)
        if not contracts:
            msg = "No active contract found for this tenant."
            raise Http404(msg)

        contracts.sort(key=lambda c: priority.get(c.status, 99))
        return contracts[0]


class RentalContractTerminateView(LoginRequiredMixin, View):
    """Allow either party to terminate an active lease with a recorded reason."""

    def post(self, request, pk):
        contract = get_object_or_404(
            RentalContract.objects.select_related(
                "tenant__user", "unit__building__property_ref__landlord__user",
            ).filter(
                Q(tenant__user=request.user)
                | Q(unit__building__property_ref__landlord__user=request.user)
            ),
            pk=pk,
        )
        reason = request.POST.get("reason", "")
        try:
            RentalContractService.terminate(
                contract=contract, actor=request.user, reason=reason,
            )
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)
        else:
            landlord = contract.unit.building.property_ref.landlord
            counterparty = (
                landlord.user if request.user.pk == contract.tenant.user_id
                else contract.tenant.user
            )
            send_notification(
                recipient=counterparty,
                title=_("Rental contract terminated"),
                message=(
                    _(
                        "Contract %(number)s was terminated by %(name)s. "
                        "Reason: %(reason)s"
                    )
                    % {
                        "number": contract.contract_number,
                        "name": request.user.full_name,
                        "reason": reason.strip(),
                    }
                ),
                notification_type=NotificationType.SYSTEM,
                related_object=contract,
            )
            messages.success(request, _("The rental contract has been terminated."))

        if request.user.pk == contract.tenant.user_id:
            return redirect("rentals:tenant-lease-detail")
        return redirect("rentals:landlord-rental-contract-detail", pk=contract.slug)


class TenantContractExtensionRequestView(TenantRequiredMixin, View):
    def post(self, request, pk):
        contract = get_object_or_404(
            RentalContract.objects.select_related(
                "unit__building__property_ref__landlord__user"
            ),
            pk=pk,
            tenant=self.get_tenant(),
        )
        form = ContractExtensionRequestForm(request.POST)
        if not form.is_valid():
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
            return redirect("rentals:tenant-lease-detail")
        try:
            extension = ContractExtensionService.request_extension(
                contract=contract,
                tenant=self.get_tenant(),
                requested_end_date=form.cleaned_data["requested_end_date"],
            )
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)
            return redirect("rentals:tenant-lease-detail")
        send_notification(
            recipient=contract.unit.building.property_ref.landlord.user,
            title=_("Contract extension requested"),
            message=(
                _(
                    "%(tenant)s requested to extend contract %(contract)s "
                    "until %(date)s."
                )
            )
            % {
                "tenant": request.user.full_name,
                "contract": contract.contract_number,
                "date": extension.requested_end_date,
            },
            notification_type=NotificationType.SYSTEM,
            related_object=extension,
        )
        messages.success(request, _("Your extension request was sent to the landlord."))
        return redirect("rentals:tenant-lease-detail")
