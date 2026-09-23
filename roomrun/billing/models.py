from core.models import BaseModel
from core.utils import safe_reverse
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from rentals.models import RentalContract
from utils.enums import ChargeStatus
from utils.enums import ChargeType
from utils.enums import PaymentMethod
from utils.enums import PaymentProvider
from utils.enums import PaymentStatus


# CHARGE
class Charge(BaseModel):
    """
    Represents a financial charge associated with a rental contract.
    Each charge has a unique number, a type, and a status.
    """

    reference_field = "charge_number"
    reference_prefix = "CHG"

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    contract = models.ForeignKey(
        RentalContract,
        on_delete=models.PROTECT,  # Prevents deletion if charges exist
        related_name="charges",
        verbose_name=_("Rental contract"),
        help_text=_("The rental contract this charge belongs to."),
    )

    charge_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
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

    amount = MoneyField(  # Changed to MoneyField for consistency
        max_digits=12,
        decimal_places=2,
        default_currency="XAF",
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
        return safe_reverse("billing:charge-detail", kwargs={"pk": self.id})

    def clean(self):
        super().clean()
        if self.amount and self.amount <= Money(0, self.amount.currency):
            raise ValidationError(_("Charge amount must be greater than zero."))

    @property
    def total_paid(self) -> Money:
        total = Money(0, self.amount.currency)
        for payment in self.payments.filter(status=PaymentStatus.COMPLETED):
            total += payment.amount
        return total

    @property
    def balance_due(self) -> Money:
        return max(self.amount - self.total_paid, Money(0, self.amount.currency))


    @property
    def is_overdue(self) -> bool:
        return (
            self.balance_due.amount > 0
            and self.due_date < timezone.localdate()
        )

    def refresh_status(self) -> None:
        zero = Money(0, self.amount.currency)

        if self.balance_due.amount == zero:
            status = ChargeStatus.PAID
        elif self.total_paid.amount > zero:
            status = ChargeStatus.PARTIAL
        elif self.is_overdue:
            status = ChargeStatus.OVERDUE
        else:
            status = ChargeStatus.PENDING

        if self.status != status:
            self.status = status
            self.save(update_fields=["status", "updated_at"])

# PAYEMENT
class Payment(BaseModel):
    """
    Represents a payment made against a financial charge.
    Each payment has a unique number and a status tracking its lifecycle.
    """

    reference_field = "payment_number"
    reference_prefix = "PAY"

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    payment_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Payment number"),
        help_text=_("Auto-generated unique identifier for the payment."),
        # Generation logic must be added via a signals.py
    )

    charge = models.ForeignKey(
        Charge,
        on_delete=models.PROTECT,  # Prevents deletion if payments exist
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

    provider = models.CharField(
        max_length=30,
        blank=True,
        choices=PaymentProvider.choices,
        verbose_name=_("Payment provider"),
        help_text=_(
            "External payment provider used to process the payment."
        ),
    )

    operator = models.CharField(
        max_length=30,
        blank=True,
        verbose_name=_("Operator"),
        help_text=_("Mobile money operator used for the payment."),
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

    provider_reference = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("Transaction reference"),
        help_text=_(
            "External transaction reference returned by the payment gateway."
        ),
    )

    external_reference = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
        verbose_name=_("External reference"),
        help_text=_(
            "Unique reference used to identify this payment externally."
        ),
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
        return safe_reverse("billing:payment-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validations:
        1. Amount must be positive.
        2. When status is PAID, paid_at must be set and not in the future.
        3. When status is PAID, paid_at must be provided.
        """
        super().clean()
        if self.amount and self.amount <= Money(0, self.amount.currency):
            raise ValidationError(_("Payment amount must be greater than zero."))

        if self.charge_id and self.amount.currency != self.charge.amount.currency:
            raise ValidationError(_("Payment and charge currencies must match."))

        if self.status == PaymentStatus.COMPLETED:
            if not self.paid_at:
                raise ValidationError(
                    _("Paid at date is required when status is COMPLETED.")
                )
            from django.utils import timezone  # noqa: PLC0415

            if self.paid_at > timezone.now():
                raise ValidationError(_("Paid at date cannot be in the future."))

        if self.status != PaymentStatus.COMPLETED and self.paid_at:
            raise ValidationError(
                _("Paid at date should only be set when status is COMPLETED.")
            )

        if self.status == PaymentStatus.COMPLETED and self.charge_id:
            previous_total = Money(0, self.charge.amount.currency)
            for payment in self.charge.payments.filter(
                status=PaymentStatus.COMPLETED
            ).exclude(pk=self.pk):
                previous_total += payment.amount
            if previous_total + self.amount > self.charge.amount:
                raise ValidationError(
                    _("A payment cannot exceed the remaining balance.")
                )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.charge.refresh_status()


# RECEIPT
class Receipt(BaseModel):
    """
    Represents a receipt issued for a completed payment.
    Each receipt has a unique number and is linked to exactly one payment.
    """

    reference_field = "receipt_number"
    reference_prefix = "RCP"

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    receipt_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
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
        return safe_reverse("billing:receipt-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validation:
        A receipt can only be created for a payment that is COMPLETED.
        """
        super().clean()
        if self.payment and self.payment.status != PaymentStatus.COMPLETED:
            raise ValidationError(
                _("Receipts can only be issued for completed payments.")
            )
