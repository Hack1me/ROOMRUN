from __future__ import annotations

import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.signing import BadSignature
from django.core.signing import SignatureExpired
from django.core.signing import TimestampSigner
from django.utils.translation import gettext_lazy as _

_TOKEN_SEP = ":"  # noqa: S105


class OtpTokenError(ValueError):
    """Raised when an OTP token cannot be used."""


class OtpTokenExpiredError(OtpTokenError):
    """Raised when an OTP token is expired."""


def generate_otp_code(length: int = 6) -> str:
    """Generate a numeric OTP with the requested number of digits."""
    length = max(length, 4)
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"


def hash_otp_code(code: str) -> str:
    """Hash a plaintext OTP using Django's password hasher."""
    return make_password(code)


def verify_otp_code(code: str, hashed: str) -> bool:
    """Return whether an OTP matches its stored hash."""
    if not hashed:
        return False
    return check_password(code, hashed)


def create_otp_token(otp_id: str, user_id: str, purpose: str) -> str:
    payload = _TOKEN_SEP.join([str(otp_id), str(user_id), purpose])
    signer = TimestampSigner(salt=f"otp-token-{purpose}")
    return signer.sign(payload)


def validate_otp_token(signed_token: str, purpose: str) -> dict[str, str]:
    max_age = getattr(settings, "OTP_VALID_MINUTES", 10) * 60
    signer = TimestampSigner(salt=f"otp-token-{purpose}")

    try:
        payload = signer.unsign(signed_token, max_age=max_age)
    except SignatureExpired as err:
        msg = _("The verification code has expired.")
        raise OtpTokenExpiredError(msg) from err
    except BadSignature as err:
        msg = _("The verification link is invalid.")
        raise OtpTokenError(msg) from err

    parts = payload.split(_TOKEN_SEP)
    if len(parts) != 3:  # noqa: PLR2004
        msg = _("The verification link is invalid.")
        raise OtpTokenError(msg)

    otp_id, user_id, embedded_purpose = parts
    if embedded_purpose != purpose:
        msg = _("This code does not match the requested operation.")
        raise OtpTokenError(msg)

    return {"otp_id": otp_id, "user_id": user_id, "purpose": purpose}


def _cooldown_key(user_id: str, purpose: str) -> str:
    return f"otp_cooldown:{purpose}:{user_id}"


def check_cooldown(user_id: str, purpose: str) -> tuple[bool, int]:
    key = _cooldown_key(user_id, purpose)
    remaining = cache.ttl(key) if hasattr(cache, "ttl") else None
    if remaining is not None and remaining > 0:
        return True, remaining
    if cache.get(key):
        return True, getattr(settings, "OTP_REQUEST_COOLDOWN_SECONDS", 60)
    return False, 0


def set_cooldown(user_id: str, purpose: str) -> None:
    timeout = getattr(settings, "OTP_REQUEST_COOLDOWN_SECONDS", 60)
    cache.set(_cooldown_key(user_id, purpose), value=True, timeout=timeout)
