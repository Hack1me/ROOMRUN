import json
import logging

from billing.forms import LandlordChargeForm
from billing.models import Charge
from billing.models import Payment
from billing.services.charge_service import ChargeService
from billing.services.gateways import verify_webhook_signature
from billing.services.payment_service import PaymentService
from billing.services.payment_service import PaymentServiceError
from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView
from django.views.generic import ListView
from djmoney.money import Money
from phonenumber_field.formfields import PhoneNumberField
from properties.mixins import LandlordRequiredMixin
from rentals.mixins import TenantRequiredMixin
from rentals.models import RentalContract
from rentals.services import RentalContractService
from utils.enums import PaymentMethod
from utils.enums import PaymentProvider
from utils.enums import PaymentStatus

logger = logging.getLogger(__name__)

DECEMBER_MONTH = 12
MIN_PHONE_NUMBER_LENGTH = 8


class BaseWebhookView(View):
    """
    Base class for provider webhooks.

    Rejects unauthenticated requests and acknowledges authenticated deliveries.
    """

    provider: str = ""

    def process(self, payload: dict) -> str | None:
        """Extract the transaction reference from the payload."""
        raise NotImplementedError

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):  # noqa: PLR0911
        signature_header = {
            PaymentProvider.CAMPAY: "HTTP_X_CAMPAY_SIGNATURE",
            PaymentProvider.DIGIPAY: "HTTP_X_DIGIPAY_SIGNATURE",
        }.get(self.provider)
        signature = request.META.get(signature_header, "") if signature_header else ""
        try:
            if not verify_webhook_signature(self.provider, request.body, signature):
                logger.warning(
                    "%s webhook: invalid or missing signature", self.provider
                )
                return HttpResponse(status=401)
        except Exception:
            logger.exception(
                "%s webhook: signature verification unavailable", self.provider
            )
            return HttpResponse(status=401)
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError, UnicodeDecodeError:
            logger.warning("%s webhook: invalid JSON", self.provider)
            return HttpResponse(status=200)

        transaction_reference = self.process(payload)
        if not transaction_reference:
            logger.warning(
                "%s webhook: no reference | payload=%s", self.provider, payload
            )
            return HttpResponse(status=200)

        logger.info(
            "%s webhook received | ref=%s", self.provider, transaction_reference
        )

        try:
            payment = PaymentService().handle_provider_notification(
                provider=self.provider,
                transaction_reference=transaction_reference,
            )
        except PaymentServiceError:
            logger.exception(
                "%s webhook: service error | ref=%s",
                self.provider,
                transaction_reference,
            )
            return HttpResponse(status=200)
        except Exception:
            logger.exception(
                "%s webhook: unexpected error | ref=%s",
                self.provider,
                transaction_reference,
            )
            return HttpResponse(status=200)

        if payment is None:
            logger.warning(
                "%s webhook: unknown ref | ref=%s", self.provider, transaction_reference
            )
            return HttpResponse(status=200)

        logger.info(
            "%s webhook processed | payment=%s", self.provider, payment.payment_number
        )
        return HttpResponse(status=200)


class CamPayWebhookView(BaseWebhookView):
    provider = PaymentProvider.CAMPAY

    def process(self, payload):
        return payload.get("reference")


class DigiPayWebhookView(BaseWebhookView):
    provider = PaymentProvider.DIGIPAY

    def process(self, payload):
        # Adapte selon le format réel du webhook DigiPay
        return (
            payload.get("transaction_id")
            or payload.get("transactionId")
            or payload.get("reference")
        )


class PaymentInitiationForm(forms.Form):
    phone_number = PhoneNumberField(
        region="CM",
        label=_("Mobile Money phone number"),
        widget=forms.TextInput(
            attrs={"autocomplete": "tel", "placeholder": "+237 6XX XXX XXX"}
        ),
    )


class TenantChargeListView(TenantRequiredMixin, ListView):
    template_name = "dashboard/billing/tenant/charge_list.html"
    context_object_name = "charges"

    def get_queryset(self):
        return (
            Charge.objects.filter(
                contract__tenant=self.get_tenant(),
                contract__status__in=["SIGNED", "ACTIVE"],
            )
            .exclude(status="PAID")
            .select_related("contract__unit")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.get_tenant()
        payments = list(
            Payment.objects.filter(charge__contract__tenant=tenant)
            .select_related(
                "charge__contract__unit__building__property_ref",
                "charge__contract__tenant__user",
            )
            .order_by("-created_at")[:100]
        )
        for payment in payments:
            payment.display_date = timezone.localtime(
                payment.paid_at or payment.created_at
            )

        outstanding_total = sum(
            (charge.balance_due for charge in context["charges"]),
            Money(0, "XAF"),
        )
        context.update(
            payments=payments,
            outstanding_total=outstanding_total,
            payment_count=len(payments),
            completed_payment_count=sum(
                payment.status == PaymentStatus.COMPLETED for payment in payments
            ),
        )
        return context


class LandlordChargeListView(LandlordRequiredMixin, ListView):
    template_name = "dashboard/billing/landlord/charge_list.html"
    context_object_name = "charges"
    paginate_by = 25

    def get_queryset(self):
        return (
            Charge.objects.filter(
                contract__unit__building__property_ref__landlord=self.get_landlord()
            )
            .select_related(
                "contract__tenant__user",
                "contract__unit__building__property_ref",
            )
            .order_by("-created_at")
        )


class LandlordChargeCreateView(LandlordRequiredMixin, FormView):
    template_name = "dashboard/billing/landlord/charge_form.html"
    form_class = LandlordChargeForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["landlord"] = self.get_landlord()
        return kwargs

    def form_valid(self, form):
        try:
            charge = ChargeService.create_for_landlord(
                landlord=self.get_landlord(),
                data=form.cleaned_data,
                actor=self.request.user,
            )
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(
            self.request,
            _("Charge %(number)s was created and the tenant was notified.")
            % {"number": charge.charge_number},
        )
        return redirect("billing:landlord-charge-list")


class TenantContractPaymentView(TenantRequiredMixin, View):
    """Prepare or resume the initial payment for the tenant's signed contract."""

    def get(self, request, pk):
        contract = get_object_or_404(
            RentalContract.objects.select_related("unit"),
            pk=pk,
            tenant=self.get_tenant(),
            status__in=["SIGNED", "ACTIVE"],
        )
        charge = Charge.objects.filter(
            contract=contract, charge_type="INITIAL_PAYMENT"
        ).first()
        if contract.status == "SIGNED" and (
            charge is None or charge.balance_due.amount > 0
        ):
            try:
                payment = RentalContractService.create_initial_payment(
                    contract=contract,
                    payment_method=PaymentMethod.MOBILE_MONEY,
                )
            except ValidationError as exc:
                for error in exc.messages:
                    messages.error(request, error)
                return redirect("rentals:tenant-lease-detail")
            charge = payment.charge
        if charge and charge.balance_due.amount > 0:
            return redirect("billing:tenant-payment-initiate", pk=charge.slug)
        if contract.status == "SIGNED":
            try:
                RentalContractService.activate(contract=contract)
            except ValidationError as exc:
                messages.error(request, exc.messages[0])
                return redirect("rentals:tenant-lease-detail")
        messages.info(
            request, _("The initial payment for this contract is already complete.")
        )
        return redirect("rentals:tenant-lease-detail")


class TenantPaymentInitiateView(TenantRequiredMixin, View):
    template_name = "dashboard/billing/tenant/payment_form.html"

    def get_charge(self):
        return get_object_or_404(
            Charge.objects.select_related("contract__unit"),
            pk=self.kwargs["pk"],
            contract__tenant=self.get_tenant(),
            contract__status__in=["SIGNED", "ACTIVE"],
            status__in=["PENDING", "PARTIAL", "OVERDUE"],
        )

    def get(self, request, *args, **kwargs):
        return render(
            request,
            self.template_name,
            {
                "charge": self.get_charge(),
                "form": PaymentInitiationForm(
                    initial={"phone_number": self.request.user.phone}
                ),
            },
        )

    def post(self, request, *args, **kwargs):
        charge = self.get_charge()
        form = PaymentInitiationForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"charge": charge, "form": form})
        payment = Payment.objects.filter(
            charge=charge, status=PaymentStatus.PENDING
        ).first()
        if payment and payment.provider_reference:
            return redirect("billing:tenant-payment-sync", pk=payment.slug)
        provider = (
            str(getattr(settings, "DEFAULT_PAYMENT_PROVIDER", PaymentProvider.DIGIPAY))
            .strip()
            .upper()
        )
        if provider not in PaymentProvider.values:
            form.add_error(None, _("The configured payment provider is invalid."))
            return render(request, self.template_name, {"charge": charge, "form": form})
        if payment is None:
            payment = Payment.objects.create(
                charge=charge,
                amount=charge.balance_due,
                payment_method=PaymentMethod.MOBILE_MONEY,
                provider=provider,
            )
        elif payment.provider != provider:
            # A pending payment without a provider transaction reference can
            # safely be retried through the provider currently selected in env.
            payment.provider = provider
            payment.save(update_fields=["provider", "updated_at"])

        try:
            PaymentService().initiate(
                payment=payment, phone_number=form.cleaned_data["phone_number"]
            )
        except (PaymentServiceError, ValidationError) as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, {"charge": charge, "form": form})
        return redirect("billing:tenant-payment-sync", pk=payment.slug)


class TenantPaymentSynchronizeView(TenantRequiredMixin, View):
    template_name = "dashboard/billing/tenant/payment_status.html"

    def get(self, request, pk):
        payment = get_object_or_404(
            Payment.objects.select_related("charge__contract"),
            pk=pk,
            charge__contract__tenant=self.get_tenant(),
        )
        if payment.status == PaymentStatus.PENDING and payment.provider_reference:
            try:
                PaymentService().synchronize(payment=payment)
            except (PaymentServiceError, ValidationError) as exc:
                messages.warning(
                    request,
                    _("Could not verify the payment status: %(detail)s")
                    % {"detail": str(exc)},
                )
            payment.refresh_from_db()
        return render(request, self.template_name, {"payment": payment})
