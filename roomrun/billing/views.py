import contextlib
import json
import logging

from billing.models import Charge
from billing.models import Payment
from billing.services.payment_service import PaymentService
from billing.services.payment_service import PaymentServiceError
from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView
from rentals.mixins import TenantRequiredMixin
from utils.enums import PaymentMethod
from utils.enums import PaymentProvider
from utils.enums import PaymentStatus

logger = logging.getLogger(__name__)


class BaseWebhookView(View):
    """
    Base class for provider webhooks.

    Always returns 200 OK to prevent provider retries.
    """

    provider: str = ""

    def process(self, payload: dict) -> str | None:
        """Extract the transaction reference from the payload."""
        raise NotImplementedError

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
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
        return payload.get("transaction_id") or payload.get("reference")


class PaymentInitiationForm(forms.Form):
    phone_number = forms.CharField(max_length=32, label="Phone number")


class TenantChargeListView(TenantRequiredMixin, ListView):
    template_name = "dashboard/billing/tenant/charge_list.html"
    context_object_name = "charges"

    def get_queryset(self):
        return (
            Charge.objects.filter(
                contract__tenant=self.get_tenant(),
                contract__status="ACTIVE",
            )
            .exclude(status="PAID")
            .select_related("contract__unit")
        )


class TenantPaymentInitiateView(TenantRequiredMixin, View):
    template_name = "dashboard/billing/tenant/payment_form.html"

    def get_charge(self):
        return get_object_or_404(
            Charge.objects.select_related("contract__unit"),
            pk=self.kwargs["pk"],
            contract__tenant=self.get_tenant(),
            contract__status="ACTIVE",
            status__in=["PENDING", "PARTIAL", "OVERDUE"],
        )

    def get(self, request, *args, **kwargs):
        return render(
            request,
            self.template_name,
            {"charge": self.get_charge(), "form": PaymentInitiationForm()},
        )

    def post(self, request, *args, **kwargs):
        charge = self.get_charge()
        form = PaymentInitiationForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"charge": charge, "form": form})
        payment = Payment.objects.filter(
            charge=charge, status=PaymentStatus.PENDING, provider_reference__isnull=True
        ).first()
        if not payment:
            payment = Payment.objects.create(
                charge=charge,
                amount=charge.balance_due,
                payment_method=PaymentMethod.MOBILE_MONEY,
            )
        try:
            PaymentService().initiate(
                payment=payment, phone_number=form.cleaned_data["phone_number"]
            )
        except (PaymentServiceError, ValidationError) as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, {"charge": charge, "form": form})
        return redirect("billing:tenant-payment-sync", pk=payment.pk)


class TenantPaymentSynchronizeView(TenantRequiredMixin, View):
    def get(self, request, pk):
        payment = get_object_or_404(
            Payment.objects.select_related("charge__contract"),
            pk=pk,
            charge__contract__tenant=self.get_tenant(),
        )
        if payment.status == PaymentStatus.PENDING and payment.provider_reference:
            with contextlib.suppress(PaymentServiceError, ValidationError):
                PaymentService().synchronize(payment=payment)
        return redirect("billing:tenant-charge-list")
