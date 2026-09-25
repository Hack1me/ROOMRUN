# billing/services/gateways/campay.py

import logging
import re
from decimal import Decimal
from typing import Any

from campay.sdk import Client as CamPayClient
from django.conf import settings

from .base import GatewayInitResult
from .base import GatewayStatusResult
from .base import PaymentGateway
from .base import PaymentGatewayError

logger = logging.getLogger(__name__)

CURRENCY = "XAF"


class CamPayGateway(PaymentGateway):
    """Adapter for the CamPay provider."""

    provider = "CAMPAY"

    def __init__(self) -> None:
        self.client = CamPayClient(
            {
                "app_username": settings.CAMPAY_USERNAME,
                "app_password": settings.CAMPAY_PASSWORD,
                "environment": settings.CAMPAY_ENVIRONMENT,
            }
        )

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
        """Initiate a CamPay collection."""
        normalized_phone = re.sub(r"[\s()+-]", "", phone_number)
        payload = {
            "amount": str(amount),
            "currency": CURRENCY,
            "from": normalized_phone,
            "description": metadata.get("description", "") if metadata else "",
            "external_reference": external_reference,
        }

        logger.info(
            "CamPay collect | ref=%s | phone=%s | amount=%s",
            external_reference, phone_number, amount,
        )

        try:
            response = self.client.initCollect(payload)
        except Exception as exc:
            logger.exception(
                "CamPay initiate failed | ref=%s", external_reference
            )
            message = "CamPay could not initiate the payment."
            raise PaymentGatewayError(message) from exc

        # CamPay returns {"status": "FAILED", "message": "..."} on error.
        if response.get("status") == "FAILED" or "reference" not in response:
            message = response.get("message", "Unknown CamPay error.")
            logger.error("CamPay collect failed | ref=%s | %s", external_reference, message)  # noqa: E501
            raise PaymentGatewayError(message)

        reference = response.get("reference")
        if not reference:
            logger.error("CamPay collect: no reference | ref=%s", external_reference)
            msg = "CamPay did not return a reference."
            raise PaymentGatewayError(msg)

        logger.info("CamPay collect OK | ref=%s | tx=%s", external_reference, reference)

        return GatewayInitResult(
            transaction_id=reference,
            status=response.get("status", "PENDING"),
            raw=response,
        )

    # -------------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------------

    def get_transaction_status(self, transaction_id: str) -> GatewayStatusResult:
        """Get a CamPay transaction's status."""
        response = self.client.get_transaction_status({"reference": transaction_id})

        if response.get("status") == "" or (
            response.get("message") and not response.get("status")
        ):
            message = response.get("message", "Unknown CamPay error.")
            logger.error("CamPay status failed | ref=%s | %s", transaction_id, message)
            raise PaymentGatewayError(message)

        amount_raw = response.get("amount")
        amount = Decimal(str(amount_raw)) if amount_raw else None

        return GatewayStatusResult(
            transaction_id=response.get("reference", transaction_id),
            status=response.get("status", "UNKNOWN"),
            amount=amount,
            raw=response,
        )

    # -------------------------------------------------------------------------
    # Webhook
    # -------------------------------------------------------------------------

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """TODO: implement once CamPay's signing method is known."""
        return True
