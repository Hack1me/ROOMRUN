# billing/services/gateways/digipay.py

import logging
import re
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
        try:
            self.client = DigiPay(api_key=settings.DIGIPAY_API_KEY)
        except Exception as exc:
            msg = "DigiPay is not configured correctly."
            raise PaymentGatewayError(msg) from exc

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
        # DigiPay's installed SDK accepts its own argument set; merchant
        # references belong in metadata and the amount must be JSON numeric.
        provider_metadata = dict(metadata or {})
        provider_metadata["external_reference"] = external_reference
        normalized_phone = re.sub(r"[\s()-]", "", phone_number)
        normalized_phone = normalized_phone.removeprefix("+")
        logger.info(
            "DigiPay initiate | ref=%s | phone=%s | amount=%s",
            external_reference,
            phone_number,
            amount,
        )
        try:
            response = self.client.payments.initiate(
                amount=float(amount),
                customer_phone=normalized_phone,
                customer_email=email,
                metadata=provider_metadata,
                webhook_url=settings.DIGIPAY_WEBHOOK_URL or None,
            )
        except Exception as exc:
            logger.exception("DigiPay initiate failed | ref=%s", external_reference)
            raise PaymentGatewayError(str(exc)) from exc

        transaction_id = response.get("transaction_id")
        if not transaction_id:
            msg = "DigiPay did not return a transaction identifier."
            raise PaymentGatewayError(msg)
        logger.info("DigiPay initiate OK | ref=%s", external_reference)

        return GatewayInitResult(
            transaction_id=transaction_id,
            status=str(response.get("status", "PENDING")).upper(),
            raw=response,
        )

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
                status=str(response.get("status", "UNKNOWN")).upper(),
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
