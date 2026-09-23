# billing/services/payment_service.py

import logging

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
        # --- 1. Validate state ---
        if payment.provider != PaymentProvider.CAMPAY:
            raise ValidationError(_("This payment does not use CamPay."))

        if not payment.provider_reference:
            raise ValidationError(_("Payment has no provider transaction reference."))

        # --- 2. Query the gateway ---
        try:
            result = self.gateway.get_transaction_status(payment.provider_reference)
        except PaymentGatewayError as exc:
            logger.exception(
                "CamPay status check failed | payment=%s",
                payment.payment_number,
            )
            raise PaymentServiceError(
                _("Unable to verify the payment status. Please try again.")
            ) from exc

        provider_status = result.status
        update_fields: list[str] = []

        # --- 3. Map provider status to our status ---
        if provider_status == "SUCCESSFUL":
            if result.amount is not None and result.amount != payment.amount.amount:
                raise PaymentServiceError(_("Provider payment amount does not match."))
            payment.status = PaymentStatus.COMPLETED
            if not payment.paid_at:
                payment.paid_at = timezone.now()
            update_fields = ["status", "paid_at", "updated_at"]

        elif provider_status == "FAILED":
            payment.status = PaymentStatus.FAILED
            payment.paid_at = None
            update_fields = ["status", "paid_at", "updated_at"]

        elif provider_status == "PENDING":
            # No change, keep pending.
            pass

        else:
            logger.warning(
                "Unknown CamPay status | payment=%s | status=%s",
                payment.payment_number,
                provider_status,
            )
            raise PaymentServiceError(
                _("Unknown payment status received from provider.")
            )

        # --- 4. Persist only if something changed ---
        if update_fields:
            payment.save(update_fields=update_fields)
            if payment.status == PaymentStatus.COMPLETED:
                from rentals.services import RentalContractService  # noqa: PLC0415
                from utils.enums import ChargeType  # noqa: PLC0415

                if payment.charge.charge_type == ChargeType.INITIAL_PAYMENT:
                    RentalContractService.activate(contract=payment.charge.contract)

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
