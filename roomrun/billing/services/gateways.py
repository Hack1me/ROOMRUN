# billing/services/gateways.py

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from campay.sdk import Client as CamPayClient
from campay.sdk.exceptions import CampayError
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

    This class contains no RoomRun business logic.
    It only translates RoomRun requests into CamPay API calls.
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

        Args:
            amount: Amount in XAF.
            phone_number: Customer phone (e.g., "2376XXXXXXXX").
            description: Short description shown to the customer.
            external_reference: Our internal unique reference.

        Returns:
            CamPayCollectResult with the provider's reference and status.

        Raises:
            CamPayGatewayError: If the API call fails.
        """
        payload = {
            "amount": str(amount),
            "currency": CURRENCY,
            "from": phone_number,
            "description": description,
            "external_reference": external_reference,
        }

        try:
            logger.info(
                "CamPay collect | ref=%s | phone=%s | amount=%s",
                external_reference, phone_number, amount,
            )
            response = self.client.initCollect(payload)
            logger.info("CamPay collect OK | ref=%s", external_reference)

            return CamPayCollectResult(
                reference=response.get("reference", ""),
                status=response.get("status", "PENDING"),
                raw=response,
            )

        except CampayError as exc:
            logger.exception("CamPay collect failed | ref=%s", external_reference)
            raise CamPayGatewayError(str(exc)) from exc
        except Exception as exc:
            logger.exception("CamPay collect unexpected error | ref=%s", external_reference)  # noqa: E501
            msg = "Unexpected error during collect."
            raise CamPayGatewayError(msg) from exc

    # -------------------------------------------------------------------------
    # Check transaction status
    # -------------------------------------------------------------------------

    def get_transaction_status(self, reference: str) -> CamPayStatusResult:
        """
        Retrieve the current status of a CamPay transaction.

        Args:
            reference: The reference returned by CamPay on collect.

        Returns:
            CamPayStatusResult with status and amount.

        Raises:
            CamPayGatewayError: If the API call fails.
        """
        try:
            response = self.client.get_transaction_status({"reference": reference})

            amount_raw = response.get("amount")
            amount = Decimal(str(amount_raw)) if amount_raw else None

            return CamPayStatusResult(
                reference=response.get("reference", reference),
                status=response.get("status", "UNKNOWN"),
                amount=amount,
                raw=response,
            )

        except CampayError as exc:
            logger.exception("CamPay status failed | ref=%s", reference)
            raise CamPayGatewayError(str(exc)) from exc
        except Exception as exc:
            logger.exception("CamPay status unexpected error | ref=%s", reference)
            msg = "Unexpected error during status check."
            raise CamPayGatewayError(msg) from exc

    # -------------------------------------------------------------------------
    # Webhook signature validation
    # -------------------------------------------------------------------------

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Validate the authenticity of an incoming CamPay webhook.

        If CamPay does not provide HMAC signatures, this method should
        return True and rely on IP allowlisting instead.
        """
        # TODO: implement once you know CamPay's webhook signing method.
        return True
