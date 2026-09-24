# billing/services/gateways/digipay.py

import logging
from decimal import Decimal
from typing import Any

from digipay import DigiPay
from django.conf import settings

from .base import GatewayInitResult
from .base import GatewayStatusResult
from .base import PaymentGateway
from .base import PaymentGatewayError

logger = logging.getLogger(__name__)


class DigiPayGateway(PaymentGateway):
    """Adapter for the DigiPay provider."""

    provider = "DIGIPAY"

    def __init__(self) -> None:
        self.client = DigiPay(api_key=settings.DIGIPAY_API_KEY)

    # -------------------------------------------------------------------------
    # Initiate
    # -------------------------------------------------------------------------

    def initiate_payment(
        self,
        *,
        amount: Decimal,
        phone_number: str,
        external_reference: str,
        email: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GatewayInitResult:
        """Initiate a DigiPay payment."""
        payload = {
            "amount": str(amount),
            "customer_phone": phone_number,
            "customer_email": email,
            "external_reference": external_reference,
            "metadata": metadata or {},
            "webhook_url": settings.DIGIPAY_WEBHOOK_URL,
        }

        try:
            logger.info(
                "DigiPay initiate | ref=%s | phone=%s | amount=%s",
                external_reference, phone_number, amount,
            )
            response = self.client.payments.initiate(**payload)
            logger.info("DigiPay initiate OK | ref=%s", external_reference)

            return GatewayInitResult(
                transaction_id=response.get("transaction_id", ""),
                status=response.get("status", "PENDING"),
                raw=response,
            )

        except Exception as exc:
            logger.exception("DigiPay initiate failed | ref=%s", external_reference)
            raise PaymentGatewayError(str(exc)) from exc

    # -------------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------------

    def get_transaction_status(self, transaction_id: str) -> GatewayStatusResult:
        """Get a DigiPay transaction's status."""
        try:
            response = self.client.payments.get_status(transaction_id)

            amount_raw = response.get("amount")
            amount = Decimal(str(amount_raw)) if amount_raw else None

            return GatewayStatusResult(
                transaction_id=response.get("transaction_id", transaction_id),
                status=response.get("status", "UNKNOWN"),
                amount=amount,
                raw=response,
            )

        except Exception as exc:
            logger.exception("DigiPay status failed | tx=%s", transaction_id)
            raise PaymentGatewayError(str(exc)) from exc

    # -------------------------------------------------------------------------
    # Webhook
    # -------------------------------------------------------------------------

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """TODO: implement once DigiPay's signing method is known."""
        return True
