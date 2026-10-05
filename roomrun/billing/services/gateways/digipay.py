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
from .base import verify_hmac_signature

logger = logging.getLogger(__name__)


class DigiPayGateway(PaymentGateway):
    """Adapter for the DigiPay provider."""

    provider = "DIGIPAY"

    def __init__(self) -> None:
        if settings.DIGIPAY_ENVIRONMENT not in {"production", "sandbox"}:
            message = "DIGIPAY_ENVIRONMENT must be 'production' or 'sandbox'."
            raise PaymentGatewayError(message)
        if not settings.DIGIPAY_API_KEY:
            message = "No DigiPay API key is configured for the selected environment."
            raise PaymentGatewayError(message)
        try:
            self.client = DigiPay(
                api_key=settings.DIGIPAY_API_KEY,
                environment=settings.DIGIPAY_ENVIRONMENT,
            )
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
            transaction_id = response.get("transaction_id")
            if not transaction_id:
                detail = response.get("message") or response.get("error")
                message = str(detail or "DigiPay did not return a transaction ID.")
                raise PaymentGatewayError(message)  # noqa: TRY301
            status = str(response.get("status", "PENDING")).upper()
            if status in {"FAILED", "FAILURE", "REJECTED", "ERROR"}:
                detail = response.get("message") or response.get("error")
                message = str(detail or "DigiPay rejected the payment request.")
                raise PaymentGatewayError(message)  # noqa: TRY301
        except Exception as exc:
            if isinstance(exc, PaymentGatewayError):
                raise
            logger.exception("DigiPay initiate failed | ref=%s", external_reference)
            detail = str(exc).replace(settings.DIGIPAY_API_KEY, "[hidden]")
            raise PaymentGatewayError(detail) from exc

        logger.info("DigiPay initiate OK | ref=%s", external_reference)

        return GatewayInitResult(
            transaction_id=transaction_id,
            status=status,
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
        """Verify DigiPay's sha256 HMAC over the original request body."""
        return verify_hmac_signature(
            payload, signature, settings.DIGIPAY_WEBHOOK_SECRET
        )
