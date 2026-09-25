import logging

from billing.models import Payment
from billing.services.gateways import PaymentGatewayError
from billing.services.gateways import get_gateway
from communications.services.notification_ser import send_notification
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from utils.enums import ChargeType
from utils.enums import NotificationType
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

        # django-phonenumber-field returns a PhoneNumber value object after
        # validation; payment gateways expect its canonical E.164 string.
        phone_number = str(phone_number).strip()
        if not phone_number:
            raise ValidationError(_("A valid mobile money phone number is required."))

        try:
            gateway = self._gateway or get_gateway(payment.provider)
            result = gateway.initiate_payment(
                amount=payment.amount.amount,
                phone_number=phone_number,
                external_reference=payment.external_reference,
                email=getattr(payment, "customer_email", None),
                metadata={"description": f"RoomRun payment {payment.payment_number}"},
            )
        except Exception as exc:
            logger.exception(
                "Payment initiation failed | payment=%s | provider=%s",
                payment.payment_number,
                payment.provider,
            )
            detail = str(exc).strip()
            if not detail:
                detail = str(_("The payment provider returned an unexpected error."))
            raise PaymentServiceError(
                _("Unable to initiate the payment: %(detail)s")
                % {"detail": detail}
            ) from exc

        payment.provider_reference = result.transaction_id

        try:
            payment.save(update_fields=[
                "provider_reference",
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
    # Helpers: synchronize validation + provider status
    # -------------------------------------------------------------------------

    _SUCCESSFUL_PROVIDER_STATUSES = frozenset({"SUCCESSFUL", "SUCCESS", "COMPLETED"})
    _FAILED_PROVIDER_STATUSES = frozenset({"FAILED", "CANCELLED", "EXPIRED"})
    _PENDING_PROVIDER_STATUSES = frozenset({"PENDING", "PROCESSING"})

    def _validate_synchronizable(self, *, payment: Payment) -> None:
        """Ensure the payment has the data required for synchronization."""
        if not payment.provider:
            raise ValidationError(_("Payment provider is required."))
        if not payment.provider_reference:
            raise ValidationError(
                _("Payment has no provider transaction reference.")
            )

    def _fetch_provider_status(self, *, payment: Payment):
        """Fetch the provider transaction status, mapping errors."""
        try:
            gateway = self._gateway or get_gateway(payment.provider)
            return gateway.get_transaction_status(payment.provider_reference)
        except (PaymentGatewayError, ValueError) as exc:
            logger.exception(
                "Gateway status failed | payment=%s | provider=%s",
                payment.payment_number,
                payment.provider,
            )
            raise PaymentServiceError(
                _("Unable to verify the payment status. Please try again.")
            ) from exc

    def _apply_provider_status(
        self, *, payment: Payment, provider_status: str
    ) -> list[str]:
        """Apply a normalized provider status to the payment."""
        if provider_status in self._SUCCESSFUL_PROVIDER_STATUSES:
            payment.status = PaymentStatus.COMPLETED
            if not payment.paid_at:
                payment.paid_at = timezone.now()
            return ["status", "paid_at", "updated_at"]
        if provider_status in self._FAILED_PROVIDER_STATUSES:
            payment.status = PaymentStatus.FAILED
            payment.paid_at = None
            return ["status", "paid_at", "updated_at"]
        if provider_status in self._PENDING_PROVIDER_STATUSES:
            return []
        logger.warning(
            "Unknown provider status | payment=%s | provider=%s | status=%s",
            payment.payment_number,
            payment.provider,
            provider_status,
        )
        raise PaymentServiceError(
            _("Unknown payment status received from provider.")
        )

    # -------------------------------------------------------------------------
    # Post-sync helpers
    # -------------------------------------------------------------------------

    def _notify_payment_completed(self, *, payment: Payment) -> None:
        """Send tenant/landlord notifications for a completed payment."""
        try:
            contract = payment.charge.contract
            property_ref = contract.unit.building.property_ref
            amount = f"{payment.amount.amount:,.0f}"
            send_notification(
                recipient=contract.tenant.user,
                title=_("Payment confirmed"),
                message=_(
                    "Your payment %(reference)s of %(amount)s FCFA was "
                    "completed for %(property)s."
                )
                % {
                    "reference": payment.payment_number,
                    "amount": amount,
                    "property": property_ref.name,
                },
                notification_type=NotificationType.PAYMENT,
                related_object=payment,
            )
            send_notification(
                recipient=property_ref.landlord.user,
                title=_("Tenant payment received"),
                message=_(
                    "%(tenant)s paid %(amount)s FCFA for %(property)s."
                )
                % {
                    "tenant": contract.tenant.user.full_name,
                    "amount": amount,
                    "property": property_ref.name,
                },
                notification_type=NotificationType.PAYMENT,
                related_object=payment,
            )
        except Exception:
            logger.exception(
                "Could not create notifications for payment %s",
                payment.payment_number,
            )

    def _schedule_completion_notifications(
        self, *, payment: Payment, previous_status: str
    ) -> None:
        """Schedule completion notifications on transaction commit."""
        if previous_status == PaymentStatus.COMPLETED:
            return
        if payment.status != PaymentStatus.COMPLETED:
            return

        def notify_payment_completed() -> None:
            self._notify_payment_completed(payment=payment)

        transaction.on_commit(notify_payment_completed)

    def _is_newly_completed(
        self, *, payment: Payment, previous_status: str
    ) -> bool:
        """Return True when the payment just transitioned to completed."""
        return (
            previous_status != PaymentStatus.COMPLETED
            and payment.status == PaymentStatus.COMPLETED
        )

    def _maybe_activate_initial_payment(self, *, payment: Payment) -> None:
        """Activate the contract once its initial payment completes."""
        if payment.status != PaymentStatus.COMPLETED:
            return
        if payment.charge.charge_type != ChargeType.INITIAL_PAYMENT:
            return
        from rentals.services import RentalContractService  # noqa: PLC0415

        try:
            RentalContractService.activate(contract=payment.charge.contract)
        except ValidationError:
            logger.info(
                "Initial payment completed; contract activation deferred | payment=%s",
                payment.payment_number,
            )

    def _maybe_apply_contract_extension(
        self, *, payment: Payment, previous_status: str
    ) -> None:
        """Mark a contract extension charge as paid once completed."""
        if not self._is_newly_completed(
            payment=payment, previous_status=previous_status
        ):
            return
        if payment.charge.charge_type != ChargeType.CONTRACT_EXTENSION:
            return
        from rentals.services import ContractExtensionService  # noqa: PLC0415

        try:
            ContractExtensionService.mark_paid(charge=payment.charge)
        except ValidationError:
            logger.exception(
                "Could not apply paid contract extension | payment=%s",
                payment.payment_number,
            )

    def _persist_synchronized_payment(
        self, *, payment: Payment, previous_status: str
    ) -> None:
        """Persist synchronized state and run post-sync side effects."""
        self._schedule_completion_notifications(
            payment=payment, previous_status=previous_status
        )
        self._maybe_activate_initial_payment(payment=payment)
        self._maybe_apply_contract_extension(
            payment=payment, previous_status=previous_status
        )

    # -------------------------------------------------------------------------
    # Synchronize
    # -------------------------------------------------------------------------

    @transaction.atomic
    def synchronize(self, *, payment: Payment) -> Payment:
        """Synchronize a payment with its provider."""
        self._validate_synchronizable(payment=payment)
        result = self._fetch_provider_status(payment=payment)
        previous_status = payment.status
        update_fields = self._apply_provider_status(
            payment=payment, provider_status=str(result.status).upper()
        )

        if update_fields:
            payment.save(update_fields=update_fields)
            self._persist_synchronized_payment(
                payment=payment, previous_status=previous_status
            )

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
                    provider_reference=transaction_reference,
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
