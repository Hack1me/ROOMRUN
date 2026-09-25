import contextlib
import json
import logging
from datetime import date
from datetime import timedelta

from billing.models import Charge
from billing.models import Payment
from billing.models import Withdrawal
from billing.services.payment_service import PaymentService
from billing.services.payment_service import PaymentServiceError
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
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
from utils.enums import ChargeType
from django.utils.translation import gettext_lazy as _

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
        return (
            payload.get("transaction_id")
            or payload.get("transactionId")
            or payload.get("reference")
        )


class PaymentInitiationForm(forms.Form):
    phone_number = PhoneNumberField(
        region="CM",
        label=_("Mobile Money phone number"),
        widget=forms.TextInput(attrs={"autocomplete": "tel", "placeholder": "+237 6XX XXX XXX"}),
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
        if contract.status == "SIGNED" and (charge is None or charge.balance_due.amount > 0):
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
        messages.info(request, _("The initial payment for this contract is already complete."))
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
        if not payment:
            payment = Payment.objects.create(
                charge=charge,
                amount=charge.balance_due,
                payment_method=PaymentMethod.MOBILE_MONEY,
            )
        try:
            if not payment.provider:
                provider = getattr(settings, "DEFAULT_PAYMENT_PROVIDER", PaymentProvider.CAMPAY)
                if provider not in PaymentProvider.values:
                    raise ValidationError(_("The configured payment provider is invalid."))
                payment.provider = provider
                payment.save(update_fields=["provider", "updated_at"])
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
            with contextlib.suppress(PaymentServiceError, ValidationError):
                PaymentService().synchronize(payment=payment)
            payment.refresh_from_db()
        return render(request, self.template_name, {"payment": payment})


def landlord_wallet_balance(landlord):
    """Calculate withdrawable XAF from settled tenant payments less reserved payouts."""
    credits_total = Payment.objects.filter(
        charge__contract__unit__building__property_ref__landlord=landlord,
        status=PaymentStatus.COMPLETED,
    ).aggregate(total=Sum("amount"))["total"]
    debits_total = Withdrawal.objects.filter(
        landlord=landlord,
        status__in=[Withdrawal.Status.PENDING, Withdrawal.Status.COMPLETED],
    ).aggregate(total=Sum("amount"))["total"]
    # django-money's Sum on a MoneyField returns the raw Decimal amount. Convert
    # both aggregates back to Money before doing currency-aware arithmetic.
    credits = Money(credits_total or 0, "XAF")
    debits = Money(debits_total or 0, "XAF")
    return credits - debits


class LandlordWalletView(LandlordRequiredMixin, View):
    template_name = "dashboard/billing/landlord/wallet.html"

    def get_context_data(self, form=None):
        landlord = self.get_landlord()
        today = timezone.localdate()
        month_start = date(today.year, today.month, 1)
        next_month = (
            date(today.year + 1, 1, 1)
            if today.month == 12
            else date(today.year, today.month + 1, 1)
        )
        previous_month_start = month_start - timedelta(days=1)
        previous_month_start = date(
            previous_month_start.year, previous_month_start.month, 1
        )
        landlord_payments = Payment.objects.filter(
            charge__contract__unit__building__property_ref__landlord=landlord
        )
        month_totals = landlord_payments.filter(
            status=PaymentStatus.COMPLETED,
            paid_at__date__gte=month_start,
            paid_at__date__lt=next_month,
        ).aggregate(total=Sum("amount"), count=Count("pk"))
        pending_totals = landlord_payments.filter(
            status=PaymentStatus.PENDING
        ).aggregate(total=Sum("amount"), count=Count("pk"))
        failed_totals = landlord_payments.filter(
            status=PaymentStatus.FAILED
        ).aggregate(total=Sum("amount"), count=Count("pk"))
        payments = list(
            landlord_payments.select_related(
                "charge__contract__tenant__user",
                "charge__contract__unit__building__property_ref",
            ).order_by("-created_at")[:100]
        )
        for payment in payments:
            local_created = timezone.localtime(payment.created_at).date()
            event_date = timezone.localtime(payment.paid_at).date() if payment.paid_at else local_created
            if event_date >= month_start:
                payment.ui_period = "current"
            elif event_date >= previous_month_start:
                payment.ui_period = "previous"
            else:
                payment.ui_period = "older"
            payment.ui_status = {
                PaymentStatus.COMPLETED: "paid",
                PaymentStatus.PENDING: "pending",
                PaymentStatus.FAILED: "failed",
                PaymentStatus.REFUNDED: "refunded",
                PaymentStatus.CANCELLED: "failed",
            }.get(payment.status, "pending")
            payment.display_date = timezone.localtime(
                payment.paid_at or payment.created_at
            )

        outstanding_charges = Charge.objects.filter(
            contract__unit__building__property_ref__landlord=landlord,
            contract__status__in=["SIGNED", "ACTIVE"],
        ).exclude(status__in=["PAID", "CANCELLED"])
        amount_due = Money(0, "XAF")
        for charge in outstanding_charges.prefetch_related("payments"):
            amount_due += charge.balance_due

        return {
            "balance": landlord_wallet_balance(landlord),
            "withdrawals": Withdrawal.objects.filter(landlord=landlord)[:20],
            "form": form or WithdrawalRequestForm(),
            "payments": payments,
            "total_payment_count": landlord_payments.count(),
            "month_income": Money(month_totals["total"] or 0, "XAF"),
            "month_payment_count": month_totals["count"] or 0,
            "pending_amount": Money(pending_totals["total"] or 0, "XAF"),
            "pending_count": pending_totals["count"] or 0,
            "failed_amount": Money(failed_totals["total"] or 0, "XAF"),
            "failed_count": failed_totals["count"] or 0,
            "amount_due": amount_due,
            "charge_types": ChargeType.choices,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request):
        form = WithdrawalRequestForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self.get_context_data(form))
        landlord = self.get_landlord()
        with transaction.atomic():
            # Serialize wallet changes for this owner to prevent concurrent overspending.
            from users.models import Landlord
            Landlord.objects.select_for_update().get(pk=landlord.pk)
            balance = landlord_wallet_balance(landlord)
            amount = Money(form.cleaned_data["amount"], "XAF")
            if amount > balance:
                form.add_error("amount", _("The requested amount exceeds your available balance."))
            else:
                Withdrawal.objects.create(
                    landlord=landlord,
                    amount=amount,
                    phone_number=form.cleaned_data["phone_number"],
                )
                messages.success(request, _("Your withdrawal request has been recorded."))
                return redirect("billing:landlord-wallet")
        return render(request, self.template_name, self.get_context_data(form))


class WithdrawalRequestForm(forms.Form):
    amount = forms.DecimalField(min_value=5000, max_digits=12, decimal_places=2, label=_("Amount (FCFA)"))
    phone_number = forms.CharField(max_length=32, label=_("Mobile Money number"))

    def clean_phone_number(self):
        value = self.cleaned_data["phone_number"].strip()
        if len(value) < 8:
            raise forms.ValidationError(_("Enter a valid phone number."))
        return value
