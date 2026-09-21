from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import FormView
from django.views.generic import ListView
from rentals.forms import RentalApplicationForm
from rentals.forms import TenantContractSignatureForm
from rentals.mixins import TenantApplicationQuerysetMixin
from rentals.mixins import TenantRequiredMixin
from rentals.models import RentalApplication
from rentals.models import RentalContract
from rentals.services import RentalApplicationService
from rentals.services import RentalContractService
from utils.enums import ContractStatus


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
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
            return self.form_invalid(form)

        messages.success(self.request, _("Rental contract signed successfully."))
        return redirect("dashboard:tenant")
