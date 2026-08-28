from core.models import BaseModel
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from rentals.models import RentalContract
from utils.enums import ChargeStatus
from utils.enums import ChargeType
from utils.enums import PaymentMethod
from utils.enums import PaymentStatus


# CHARGE
class Charge(BaseModel):
    """
    Represents a financial charge associated with a rental contract.
    Each charge has a unique number, a type, and a status.
    """

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    contract = models.ForeignKey(
        RentalContract,
        on_delete=models.PROTECT,          # Prevents deletion if charges exist
        related_name="charges",
        verbose_name=_("Rental contract"),
        help_text=_("The rental contract this charge belongs to."),
    )

    charge_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name=_("Charge number"),
        help_text=_("Auto-generated unique identifier for the charge."),
        # Generation logic must be added via a signals.py
    )

    charge_type = models.CharField(
        max_length=30,
        choices=ChargeType.choices,
        verbose_name=_("Charge type"),
        help_text=_("Type of charge (e.g., rent, utilities, maintenance)."),
    )

    amount = MoneyField(                   # Changed to MoneyField for consistency
        max_digits=12,
        decimal_places=2,
        default_currency="USD",            # Adjust to your default currency
        verbose_name=_("Amount"),
        help_text=_("Charge amount in the local currency."),
    )

    due_date = models.DateField(
        verbose_name=_("Due date"),
        help_text=_("Date by which the charge must be paid."),
    )

    status = models.CharField(
        max_length=20,
        choices=ChargeStatus.choices,
        default=ChargeStatus.PENDING,
        verbose_name=_("Status"),
        help_text=_("Current payment status of the charge."),
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Optional details or notes about the charge."),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "charges"
        ordering = ["-due_date"]
        verbose_name = _("Charge")
        verbose_name_plural = _("Charges")

        indexes = [
            models.Index(fields=["contract"], name="charge_contract_idx"),
            models.Index(fields=["charge_type"], name="charge_type_idx"),
            models.Index(fields=["status"], name="charge_status_idx"),
            models.Index(fields=["due_date"], name="charge_due_date_idx"),
        ]

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the charge number as string representation."""
        return self.charge_number

    def get_absolute_url(self) -> str:
        """Return the canonical URL for the charge detail view."""
        return reverse("billing:charge-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validations:
        - Ensure due_date is not in the past (optional, uncomment if needed)
        """
        from datetime import date  # noqa: PLC0415
        if self.due_date and self.due_date < date.today():  # noqa: DTZ011
            raise ValidationError(_("Due date cannot be in the past."))

    def save(self, *args, **kwargs):
        """Run full validation before saving."""
        self.full_clean()
        super().save(*args, **kwargs)

#PAYEMENT
class Payment(BaseModel):
    """
    Represents a payment made against a financial charge.
    Each payment has a unique number and a status tracking its lifecycle.
    """

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    payment_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name=_("Payment number"),
        help_text=_("Auto-generated unique identifier for the payment."),
        # Generation logic must be added via a signals.py
    )

    charge = models.ForeignKey(
        Charge,
        on_delete=models.PROTECT,          # Prevents deletion if payments exist
        related_name="payments",
        verbose_name=_("Charge"),
        help_text=_("The financial charge this payment is for."),
    )

    amount = MoneyField(
        max_digits=12,
        decimal_places=2,
        default_currency="XAF",
        verbose_name=_("Amount"),
        help_text=_("Payment amount in the local currency."),
    )

    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        verbose_name=_("Payment method"),
        help_text=_("Method used to make the payment (e.g., cash, momo)."),
    )

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        verbose_name=_("Status"),
        help_text=_("Current payment status."),
    )

    transaction_reference = models.CharField(
        max_length=100,
        unique=True,
        null=True,                # Required for gateways that don't provide a reference
        blank=True,
        verbose_name=_("Transaction reference"),
        help_text=_("External reference from the payment gateway."),
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Paid at"),
        help_text=_("Date and time when the payment was successfully completed."),
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes"),
        help_text=_("Additional notes about the payment."),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")

        indexes = [
            models.Index(fields=["charge"], name="payment_charge_idx"),
            models.Index(fields=["status"], name="payment_status_idx"),
            models.Index(fields=["paid_at"], name="payment_paid_at_idx"),
            models.Index(fields=["payment_method"], name="payment_method_idx"),
        ]

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the payment number as string representation."""
        return self.payment_number

    def get_absolute_url(self) -> str:
        """Return the canonical URL for the payment detail view."""
        return reverse("billing:payment-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validations:
        1. Amount must be positive.
        2. When status is PAID, paid_at must be set and not in the future.
        3. When status is PAID, paid_at must be provided.
        """
        if self.amount and self.amount <= 0:
            raise ValidationError(_("Payment amount must be greater than zero."))

        if self.status == PaymentStatus.PAID:
            if not self.paid_at:
                raise ValidationError(
                    _("Paid at date is required when status is PAID.")
                )
            from django.utils import timezone  # noqa: PLC0415
            if self.paid_at > timezone.now():
                raise ValidationError(
                    _("Paid at date cannot be in the future.")
                )

        # When status is not PAID, paid_at should be null
        if self.status != PaymentStatus.PAID and self.paid_at:
            raise ValidationError(
                _("Paid at date should only be set when status is PAID.")
            )

    def save(self, *args, **kwargs):
        """Run full validation before saving."""
        self.full_clean()
        super().save(*args, **kwargs)

# RECEIPT
class Receipt(BaseModel):
    """
    Represents a receipt issued for a completed payment.
    Each receipt has a unique number and is linked to exactly one payment.
    """

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    receipt_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name=_("Receipt number"),
        help_text=_("Auto-generated unique identifier for the receipt."),
        # Generation logic must be added via a signals.py
    )

    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        related_name="receipt",
        verbose_name=_("Payment"),
        help_text=_("The payment for which this receipt is issued."),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "receipts"
        ordering = ["-created_at"]
        verbose_name = _("Receipt")
        verbose_name_plural = _("Receipts")

        indexes = [
            models.Index(fields=["payment"], name="receipt_payment_idx"),
            models.Index(fields=["created_at"], name="receipt_created_at_idx"),
        ]

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the receipt number as string representation."""
        return self.receipt_number

    def get_absolute_url(self) -> str:
        """Return the canonical URL for the receipt detail view."""
        return reverse("billing:receipt-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validation:
        A receipt can only be created for a payment that is COMPLETED.
        """
        if self.payment and self.payment.status != "COMPLETED":
            raise ValidationError(
                _("Receipts can only be issued for completed payments.")
            )

    def save(self, *args, **kwargs):
        """Run full validation before saving."""
        self.full_clean()
        super().save(*args, **kwargs)
