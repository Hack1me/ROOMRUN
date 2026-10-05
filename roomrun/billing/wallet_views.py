from datetime import date
from datetime import timedelta

from billing.models import Charge
from billing.models import Payment
from billing.models import Withdrawal
from billing.services.wallet_service import request_withdrawal
from billing.services.wallet_service import wallet_balance
from core.utils.enums import ChargeType
from core.utils.enums import PaymentStatus
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.db.models import Sum
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from djmoney.money import Money
from properties.mixins import LandlordRequiredMixin

DECEMBER_MONTH = 12
MIN_PHONE_NUMBER_LENGTH = 8


class LandlordWalletView(LandlordRequiredMixin, View):
    template_name = "dashboard/billing/landlord/wallet.html"

    def get_context_data(self, form=None):
        landlord = self.get_landlord()
        today = timezone.localdate()
        month_start = date(today.year, today.month, 1)
        next_month = (
            date(today.year + 1, 1, 1)
            if today.month == DECEMBER_MONTH
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
        failed_totals = landlord_payments.filter(status=PaymentStatus.FAILED).aggregate(
            total=Sum("amount"), count=Count("pk")
        )
        payments = list(
            landlord_payments.select_related(
                "charge__contract__tenant__user",
                "charge__contract__unit__building__property_ref",
            ).order_by("-created_at")[:100]
        )
        for payment in payments:
            local_created = timezone.localtime(payment.created_at).date()
            event_date = (
                timezone.localtime(payment.paid_at).date()
                if payment.paid_at
                else local_created
            )
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
            "balance": wallet_balance(landlord),
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
        try:
            request_withdrawal(
                landlord=landlord,
                amount=form.cleaned_data["amount"],
                phone_number=form.cleaned_data["phone_number"],
            )
        except ValidationError as exc:
            form.add_error("amount", exc.messages[0])
        else:
            messages.success(request, _("Your withdrawal request has been recorded."))
            return redirect("billing:landlord-wallet")
        return render(request, self.template_name, self.get_context_data(form))


class WithdrawalRequestForm(forms.Form):
    amount = forms.DecimalField(
        min_value=5000, max_digits=12, decimal_places=2, label=_("Amount (FCFA)")
    )
    phone_number = forms.CharField(max_length=32, label=_("Mobile Money number"))

    def clean_phone_number(self):
        value = self.cleaned_data["phone_number"].strip()
        if len(value) < MIN_PHONE_NUMBER_LENGTH:
            raise forms.ValidationError(_("Enter a valid phone number."))
        return value
