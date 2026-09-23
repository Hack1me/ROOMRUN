import hashlib
import hmac
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from campay.sdk import Client as CamPayClient
from django.conf import settings

logger = logging.getLogger(__name__)

CURRENCY = "XAF"


# =============================================================================
# Base exception
# =============================================================================


class PaymentGatewayError(Exception):
    """Base exception for all payment gateway errors."""


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class CamPayCollectResult:
    """Structured result for a collect call."""

    reference: str
    status: str
    raw: dict[str, Any]


@dataclass
class CamPayStatusResult:
    """Structured result for a status call."""

    reference: str
    status: str
    amount: Decimal | None
    raw: dict[str, Any]


# =============================================================================
# CamPay exception
# =============================================================================


class CamPayGatewayError(PaymentGatewayError):
    """Raised when CamPay API returns an error."""


# =============================================================================
# CamPay gateway
# =============================================================================


class CamPayGateway:
    """
    Adapter responsible for communicating with the CamPay API.

    The CamPay SDK never raises exceptions — it returns a dict with
    `status` = "FAILED" and a `message` on error. This adapter
    converts those error dicts into `CamPayGatewayError`.
    """

    def __init__(self) -> None:
        self.client = CamPayClient(
            {
                "app_username": settings.CAMPAY_USERNAME,
                "app_password": settings.CAMPAY_PASSWORD,
                "environment": settings.CAMPAY_ENVIRONMENT,  # "DEV" | "PROD"
            }
        )

    # -------------------------------------------------------------------------
    # Initiate a payment
    # -------------------------------------------------------------------------

    def collect(
        self,
        *,
        amount: Decimal,
        phone_number: str,
        description: str,
        external_reference: str,
    ) -> CamPayCollectResult:
        """
        Initiate a payment collection through CamPay.

        Raises:
            CamPayGatewayError: If the API returns an error.
        """
        payload = {
            "amount": str(amount),
            "currency": CURRENCY,
            "from": phone_number,
            "description": description,
            "external_reference": external_reference,
        }

        logger.info(
            "CamPay collect | ref=%s | phone=%s | amount=%s",
            external_reference,
            phone_number,
            amount,
        )

        response = self.client.initCollect(payload)

        # CamPay returns {"status": "FAILED", "message": "..."} on error.
        if response.get("status") == "FAILED" or (
            "message" in response and "reference" not in response
        ):
            message = response.get("message", "Unknown CamPay error.")
            logger.error(
                "CamPay collect failed | ref=%s | message=%s",
                external_reference,
                message,
            )
            raise CamPayGatewayError(message)

        reference = response.get("reference")
        if not reference:
            logger.error(
                "CamPay collect: no reference in response | ref=%s | response=%s",
                external_reference,
                response,
            )
            msg = "CamPay did not return a reference."
            raise CamPayGatewayError(msg)

        logger.info("CamPay collect OK | ref=%s | tx=%s", external_reference, reference)

        return CamPayCollectResult(
            reference=reference,
            status=response.get("status", "PENDING"),
            raw=response,
        )

    # -------------------------------------------------------------------------
    # Check transaction status
    # -------------------------------------------------------------------------

    def get_transaction_status(self, reference: str) -> CamPayStatusResult:
        """
        Retrieve the current status of a CamPay transaction.

        Raises:
            CamPayGatewayError: If the API returns an error.
        """
        response = self.client.get_transaction_status({"reference": reference})

        # CamPay returns {"status": "", "message": "..."} on error.
        if response.get("status") == "" or (
            response.get("message") and not response.get("status")
        ):
            message = response.get("message", "Unknown CamPay error.")
            logger.error(
                "CamPay status failed | ref=%s | message=%s",
                reference,
                message,
            )
            raise CamPayGatewayError(message)

        amount_raw = response.get("amount")
        amount = Decimal(str(amount_raw)) if amount_raw else None

        logger.info(
            "CamPay status OK | ref=%s | status=%s",
            reference,
            response.get("status"),
        )

        return CamPayStatusResult(
            reference=response.get("reference", reference),
            status=response.get("status", "UNKNOWN"),
            amount=amount,
            raw=response,
        )

    # -------------------------------------------------------------------------
    # Webhook signature validation
    # -------------------------------------------------------------------------

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Validate the authenticity of an incoming CamPay webhook."""
        secret = getattr(settings, "CAMPAY_WEBHOOK_SECRET", "")
        if not secret or not signature:
            return False
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
