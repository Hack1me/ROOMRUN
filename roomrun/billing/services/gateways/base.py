# billing/services/gateways/base.py

import hashlib
import hmac
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from decimal import Decimal

# =============================================================================
# Exceptions
# =============================================================================


class PaymentGatewayError(Exception):
    """Base exception for all payment gateway errors."""


class PaymentGatewayConnectionError(PaymentGatewayError):
    """Raised when the gateway cannot be reached."""


class PaymentGatewayValidationError(PaymentGatewayError):
    """Raised when the gateway rejects the request (bad input)."""


class PaymentGatewayAuthError(PaymentGatewayError):
    """Raised when credentials are invalid."""


# =============================================================================
# Result dataclasses
# =============================================================================


@dataclass
class GatewayInitResult:
    """Standard result for a payment initiation."""

    transaction_id: str  # Provider's transaction ID
    status: str  # Provider's raw status
    raw: dict[str, Any]  # Full provider response


@dataclass
class GatewayStatusResult:
    """Standard result for a status query."""

    transaction_id: str
    status: str
    amount: Decimal | None
    raw: dict[str, Any]


# =============================================================================
# Abstract base
# =============================================================================


class PaymentGateway(ABC):
    """
    Common interface for all payment gateways.
    """

    provider: str = ""  # To be set by subclasses (e.g., "CAMPAY")

    @abstractmethod
    def initiate_payment(
        self,
        *,
        amount: Decimal,
        phone_number: str,
        external_reference: str,
        email: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GatewayInitResult:
        """Initiate a payment with the provider."""

    @abstractmethod
    def get_transaction_status(self, transaction_id: str) -> GatewayStatusResult:
        """Get the current status of a transaction."""

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Validate an incoming webhook."""


def verify_hmac_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify a sha256 HMAC over the exact webhook request bytes."""
    if not secret or not signature:
        return False
    supplied = signature.removeprefix("sha256=").strip()
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied)
