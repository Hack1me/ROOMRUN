import logging

from billing.models import Payment
from billing.services.gateways import PaymentGatewayError
from billing.services.gateways import get_gateway
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from utils.enums import PaymentStatus

logger = logging.getLogger(__name__)


class PaymentServiceError(Exception):
    """Raised when a payment operation fails."""


class PaymentService:
    """
    Handles payment business logic.

    Supports multiple payment providers via a gateway factory.
    """

    def __init__(self, gateway=None):
        # Optional injection for tests.
        self._gateway = gateway

    # -------------------------------------------------------------------------
    # Initiate
    # -------------------------------------------------------------------------

    @transaction.atomic
    def initiate(
        self,
        *,
        payment: Payment,
        phone_number: str,
    ) -> Payment:
        """
        Initiate the payment with the provider stored on the payment.

        The provider must be set on the Payment instance before calling this.
        """
        if payment.status != PaymentStatus.PENDING:
            raise ValidationError(_("Only pending payments can be initiated."))

        if not payment.external_reference:
            raise ValidationError(_("Payment external reference is required."))

        if not payment.provider:
            raise ValidationError(_("Payment provider is required."))

        gateway = self._gateway or get_gateway(payment.provider)

        try:
            result = gateway.initiate_payment(
                amount=payment.amount.amount,
                phone_number=phone_number,
                external_reference=payment.external_reference,
                email=getattr(payment, "customer_email", None),
                metadata={"description": f"RoomRun payment {payment.payment_number}"},
            )
        except PaymentGatewayError as exc:
            logger.exception(
                "Payment initiation failed | payment=%s | provider=%s",
                payment.payment_number,
                payment.provider,
            )
            raise PaymentServiceError(
                _("Unable to initiate the payment. Please try again.")
            ) from exc

        payment.transaction_reference = result.transaction_id

        try:
            payment.save(update_fields=[
                "transaction_reference",
                "updated_at",
            ])
        except IntegrityError as exc:
            logger.exception(
                "Duplicate transaction_reference | ref=%s",
                result.transaction_id,
            )
            raise PaymentServiceError(
                _("This transaction reference is already used.")
            ) from exc

        logger.info(
            "Payment initiated | payment=%s | provider=%s | tx=%s",
            payment.payment_number,
            payment.provider,
            result.transaction_id,
        )
        return payment

    # -------------------------------------------------------------------------
    # Synchronize
    # -------------------------------------------------------------------------

    @transaction.atomic
    def synchronize(self, *, payment: Payment) -> Payment:
        """
        Synchronize a payment with its provider.
        """
        if not payment.provider:
            raise ValidationError(_("Payment provider is required."))

        if not payment.transaction_reference:
            raise ValidationError(
                _("Payment has no provider transaction reference.")
            )

        gateway = self._gateway or get_gateway(payment.provider)

        try:
            result = gateway.get_transaction_status(payment.transaction_reference)
        except PaymentGatewayError as exc:
            logger.exception(
                "Gateway status failed | payment=%s | provider=%s",
                payment.payment_number,
                payment.provider,
            )
            raise PaymentServiceError(
                _("Unable to verify the payment status. Please try again.")
            ) from exc

        provider_status = result.status
        update_fields: list[str] = []

        if provider_status in ("SUCCESSFUL", "SUCCESS", "COMPLETED"):
            payment.status = PaymentStatus.COMPLETED
            if not payment.paid_at:
                payment.paid_at = timezone.now()
            update_fields = ["status", "paid_at", "updated_at"]

        elif provider_status in ("FAILED", "CANCELLED", "EXPIRED"):
            payment.status = PaymentStatus.FAILED
            payment.paid_at = None
            update_fields = ["status", "paid_at", "updated_at"]

        elif provider_status in ("PENDING", "PROCESSING"):
            pass  # No change

        else:
            logger.warning(
                "Unknown provider status | payment=%s | provider=%s | status=%s",
                payment.payment_number,
                payment.provider,
                provider_status,
            )
            raise PaymentServiceError(
                _("Unknown payment status received from provider.")
            )

        if update_fields:
            payment.save(update_fields=update_fields)

        logger.info(
            "Payment synchronized | payment=%s | status=%s",
            payment.payment_number,
            payment.status,
        )
        return payment

    # -------------------------------------------------------------------------
    # Webhook handler
    # -------------------------------------------------------------------------

    @transaction.atomic
    def handle_provider_notification(
        self,
        *,
        provider: str,
        transaction_reference: str,
    ) -> Payment | None:
        """
        Handle a webhook notification from a provider.

        Returns the updated Payment, or None if unknown.
        """
        try:
            payment = (
                Payment.objects
                .select_for_update()
                .get(
                    transaction_reference=transaction_reference,
                    provider=provider,
                )
            )
        except Payment.DoesNotExist:
            logger.warning(
                "Webhook for unknown transaction | provider=%s | ref=%s",
                provider,
                transaction_reference,
            )
            return None

        logger.info(
            "Webhook processing | payment=%s | provider=%s",
            payment.payment_number,
            provider,
        )
        return self.synchronize(payment=payment)
