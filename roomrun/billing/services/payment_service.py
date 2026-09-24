# billing/services/payment_service.py

import logging
from typing import TYPE_CHECKING

from billing.models import Payment
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from utils.enums import PaymentProvider
from utils.enums import PaymentStatus

from .gateways import CamPayGateway
from .gateways import PaymentGatewayError

if TYPE_CHECKING:
    from .gateways import CamPayStatusResult

logger = logging.getLogger(__name__)


class PaymentServiceError(Exception):
    """Raised when a payment operation fails."""


class PaymentService:
    """
    Handles payment business logic.

    Orchestrates the interaction between our internal Payment model
    and the external payment gateway.
    """

    def __init__(self, gateway=None):
        self.gateway = gateway or CamPayGateway()

    # -------------------------------------------------------------------------
    # Initiation
    # -------------------------------------------------------------------------

    @transaction.atomic
    def initiate(
        self,
        *,
        payment: Payment,
        phone_number: str,
    ) -> Payment:
        """
        Initiate the payment with the configured provider.

        Args:
            payment: A Payment instance in PENDING status.
            phone_number: Customer phone number (format expected by provider).

        Returns:
            The updated Payment instance (still PENDING, awaiting confirmation).

        Raises:
            ValidationError: If the payment is not in a valid state.
            PaymentServiceError: If the gateway call fails.
        """
        # --- 1. Validate state ---
        if payment.status != PaymentStatus.PENDING:
            raise ValidationError(_("Only pending payments can be initiated."))

        if not payment.external_reference:
            raise ValidationError(_("Payment external reference is required."))

        # --- 2. Call the gateway ---
        try:
            result = self.gateway.collect(
                amount=payment.amount.amount,
                phone_number=phone_number,
                description=f"RoomRun payment {payment.payment_number}",
                external_reference=payment.external_reference,
            )
        except PaymentGatewayError as exc:
            logger.exception(
                "Payment initiation failed | payment=%s | ref=%s",
                payment.payment_number,
                payment.external_reference,
            )
            raise PaymentServiceError(
                _("Unable to initiate the payment. Please try again.")
            ) from exc

        # --- 3. Update the payment record ---
        payment.provider = PaymentProvider.CAMPAY
        payment.provider_reference = result.reference
        payment.operator = result.raw.get("operator", "")

        try:
            payment.save(
                update_fields=[
                    "provider",
                    "provider_reference",
                    "operator",
                    "updated_at",
                ]
            )
        except IntegrityError as exc:
            logger.exception(
                "Duplicate transaction_reference | ref=%s",
                result.reference,
            )
            raise PaymentServiceError(
                _("This transaction reference is already used.")
            ) from exc

        logger.info(
            "Payment initiated | payment=%s | tx=%s",
            payment.payment_number,
            result.reference,
        )
        return payment

    def _validate_synchronizable(self, *, payment: Payment) -> None:
        """Ensure the payment can be synchronized with CamPay."""
        if payment.provider != PaymentProvider.CAMPAY:
            raise ValidationError(_("This payment does not use CamPay."))

        if not payment.provider_reference:
            raise ValidationError(_("Payment has no provider transaction reference."))

    def _fetch_provider_status(self, *, payment: Payment) -> CamPayStatusResult:
        """Query the gateway for the latest provider status."""
        try:
            return self.gateway.get_transaction_status(payment.provider_reference)
        except PaymentGatewayError as exc:
            logger.exception(
                "CamPay status check failed | payment=%s",
                payment.payment_number,
            )
            raise PaymentServiceError(
                _("Unable to verify the payment status. Please try again.")
            ) from exc

    def _mark_completed(
        self, *, payment: Payment, result: CamPayStatusResult
    ) -> list[str]:
        """Apply a SUCCESSFUL provider status to the payment."""
        if result.amount is not None and result.amount != payment.amount.amount:
            raise PaymentServiceError(_("Provider payment amount does not match."))
        payment.status = PaymentStatus.COMPLETED
        if not payment.paid_at:
            payment.paid_at = timezone.now()
        return ["status", "paid_at", "updated_at"]

    def _mark_failed(self, *, payment: Payment) -> list[str]:
        """Apply a FAILED provider status to the payment."""
        payment.status = PaymentStatus.FAILED
        payment.paid_at = None
        return ["status", "paid_at", "updated_at"]

    def _apply_provider_status(
        self, *, payment: Payment, result: CamPayStatusResult
    ) -> list[str]:
        """Map the provider status onto the payment; return fields to persist."""
        if result.status == "SUCCESSFUL":
            return self._mark_completed(payment=payment, result=result)

        if result.status == "FAILED":
            return self._mark_failed(payment=payment)

        if result.status == "PENDING":
            # No change, keep pending.
            return []

        logger.warning(
            "Unknown CamPay status | payment=%s | status=%s",
            payment.payment_number,
            result.status,
        )
        raise PaymentServiceError(_("Unknown payment status received from provider."))

    def _maybe_activate_contract(self, *, payment: Payment) -> None:
        """Activate the contract when an initial payment completes."""
        from rentals.services import RentalContractService  # noqa: PLC0415
        from utils.enums import ChargeType  # noqa: PLC0415

        if payment.charge.charge_type == ChargeType.INITIAL_PAYMENT:
            RentalContractService.activate(contract=payment.charge.contract)

    def _persist_synchronized_payment(
        self, *, payment: Payment, update_fields: list[str]
    ) -> None:
        """Persist synchronized state and trigger contract activation."""
        if not update_fields:
            return
        payment.save(update_fields=update_fields)
        if payment.status == PaymentStatus.COMPLETED:
            self._maybe_activate_contract(payment=payment)

    # -------------------------------------------------------------------------
    # Confirmation
    # -------------------------------------------------------------------------

    @transaction.atomic
    def synchronize(self, *, payment: Payment) -> Payment:
        """
        Synchronize a payment with the payment provider.

        Called after the user completes the payment on their phone,
        or triggered by the provider's webhook.

        Raises:
            ValidationError: If the payment is in an invalid state.
            PaymentServiceError: If the gateway call fails.
        """
        self._validate_synchronizable(payment=payment)
        result = self._fetch_provider_status(payment=payment)
        update_fields = self._apply_provider_status(payment=payment, result=result)
        self._persist_synchronized_payment(payment=payment, update_fields=update_fields)

        logger.info(
            "Payment synchronized | payment=%s | status=%s",
            payment.payment_number,
            payment.status,
        )
        return payment

    # -------------------------------------------------------------------------
    # Cancellation (optional, for failed/abandoned payments)
    # -------------------------------------------------------------------------

    @transaction.atomic
    def cancel(self, *, payment: Payment) -> Payment:
        """
        Mark a pending payment as failed (abandoned by the user).
        """
        if payment.status != PaymentStatus.PENDING:
            raise ValidationError(_("Only pending payments can be cancelled."))

        payment.status = PaymentStatus.FAILED
        payment.save(update_fields=["status", "updated_at"])

        logger.info("Payment cancelled | payment=%s", payment.payment_number)
        return payment

    # ----------------------------------------------
    # WEBHOOK
    # -----------------------------------------------

    @transaction.atomic
    def handle_provider_notification(
        self,
        *,
        provider_reference: str,
    ) -> Payment | None:
        """
        Handle a payment notification received from CamPay.

        Called from the webhook endpoint. Returns the updated Payment,
        or None if the reference is unknown.

        Raises:
            PaymentServiceError: If the status check fails.
        """
        try:
            payment = Payment.objects.select_for_update().get(
                provider_reference=provider_reference,
                provider=PaymentProvider.CAMPAY,
            )
        except Payment.DoesNotExist:
            logger.warning(
                "Webhook received for unknown transaction | ref=%s",
                provider_reference,
            )
            return None

        logger.info(
            "Webhook processing | payment=%s | ref=%s",
            payment.payment_number,
            provider_reference,
        )

        return self.synchronize(payment=payment)
