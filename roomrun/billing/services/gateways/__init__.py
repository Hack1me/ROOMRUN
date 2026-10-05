"""Payment gateway adapters and their provider factory."""

from core.utils.enums import PaymentProvider
from django.conf import settings

from .base import GatewayInitResult
from .base import GatewayStatusResult
from .base import PaymentGateway
from .base import PaymentGatewayAuthError
from .base import PaymentGatewayConnectionError
from .base import PaymentGatewayError
from .base import PaymentGatewayValidationError
from .base import verify_hmac_signature
from .campay import CamPayGateway
from .digipay import DigiPayGateway

__all__ = [
    "CamPayGateway",
    "DigiPayGateway",
    "GatewayInitResult",
    "GatewayStatusResult",
    "PaymentGateway",
    "PaymentGatewayAuthError",
    "PaymentGatewayConnectionError",
    "PaymentGatewayError",
    "PaymentGatewayValidationError",
    "get_default_gateway",
    "get_gateway",
    "verify_webhook_signature",
]


_GATEWAY_REGISTRY: dict[str, type[PaymentGateway]] = {
    PaymentProvider.CAMPAY: CamPayGateway,
    PaymentProvider.DIGIPAY: DigiPayGateway,
}


def get_gateway(provider: str) -> PaymentGateway:
    """
    Return an instance of the gateway for the given provider.

    Args:
        provider: A value from PaymentProvider.

    Raises:
        ValueError: If the provider is unknown.
    """
    gateway_class = _GATEWAY_REGISTRY.get(provider)
    if not gateway_class:
        msg = f"Unknown payment provider: {provider}"
        raise ValueError(msg)
    return gateway_class()


def get_default_gateway() -> PaymentGateway:
    """
    Return the default gateway (configurable in settings).

    Falls back to CamPay.
    """
    default = getattr(settings, "DEFAULT_PAYMENT_PROVIDER", PaymentProvider.DIGIPAY)
    return get_gateway(default)


def verify_webhook_signature(provider: str, payload: bytes, signature: str) -> bool:
    """Verify provider signatures without initializing payment SDK clients."""
    secrets = {
        PaymentProvider.CAMPAY: getattr(settings, "CAMPAY_WEBHOOK_SECRET", ""),
        PaymentProvider.DIGIPAY: getattr(settings, "DIGIPAY_WEBHOOK_SECRET", ""),
    }
    secret = secrets.get(provider)
    return verify_hmac_signature(payload, signature, secret or "")
