from django.conf import settings
from utils.enums import PaymentProvider

from .base import GatewayInitResult
from .base import GatewayStatusResult
from .base import PaymentGateway
from .base import PaymentGatewayAuthError
from .base import PaymentGatewayConnectionError
from .base import PaymentGatewayError
from .base import PaymentGatewayValidationError
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
