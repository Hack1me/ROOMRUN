import json
import logging

from billing.models import Charge
from billing.models import Payment
from billing.services.gateways import CamPayGateway
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
from utils.enums import PaymentStatus

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class CamPayWebhookView(View):
    """
    Webhook endpoint for CamPay notifications.

    Always returns 200 OK, even on errors, to prevent CamPay from
    retrying indefinitely. Errors are logged and handled internally.
    """

    def post(self, request, *args, **kwargs):
        signature = request.headers.get("X-CamPay-Signature") or request.headers.get(
            "X-Campay-Signature"
        )
        if not CamPayGateway().verify_webhook_signature(request.body, signature):
            logger.warning("CamPay webhook: invalid signature")
            return HttpResponse(status=401)

        # --- 1. Parse JSON ---
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError, UnicodeDecodeError:
            logger.warning("CamPay webhook: invalid payload")
            return HttpResponse(status=200)

        # --- 2. Extract reference ---
        provider_reference = payload.get("reference")
        if not provider_reference:
            logger.warning("CamPay webhook: missing reference | payload=%s", payload)
            return HttpResponse(status=200)

        logger.info("CamPay webhook received | ref=%s", provider_reference)

        # --- 3. Process ---
        try:
            payment = PaymentService().handle_provider_notification(
                provider_reference=provider_reference,
            )
        except PaymentServiceError:
            logger.exception(
                "CamPay webhook: service error | ref=%s",
                provider_reference,
            )
            return HttpResponse(status=200)
        except Exception:
            logger.exception(
                "CamPay webhook: unexpected error | ref=%s",
                provider_reference,
            )
            return HttpResponse(status=200)

        # --- 4. Handle unknown reference ---
        if payment is None:
            logger.warning(
                "CamPay webhook: unknown reference | ref=%s",
                provider_reference,
            )
            # Still 200 to stop retries.
            return HttpResponse(status=200)

        logger.info(
            "CamPay webhook processed | payment=%s | status=%s",
            payment.payment_number,
            payment.status,
        )
        return HttpResponse(status=200)


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
            try:
                PaymentService().synchronize(payment=payment)
            except PaymentServiceError, ValidationError:
                pass
        return redirect("billing:tenant-charge-list")
