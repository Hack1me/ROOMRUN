
"""
OTP (One-Time Password) utilities for ROOMRUN.

Provides secure generation, hashing, verification, signed tokens,
and rate-limiting (cooldown) for OTP operations.
"""

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

# -------------------------------------------------------------------------
# Constants (single source of truth)
# -------------------------------------------------------------------------

TOKEN_SEPARATOR = ":"          # Separator for token payload parts  # noqa: S105
DEFAULT_OTP_LENGTH = 6         # Default number of digits
DEFAULT_TOKEN_VALID_MINUTES = 10
DEFAULT_COOLDOWN_SECONDS = 60
MIN_OTP_LENGTH = 4             # Minimum allowed length for security


# -------------------------------------------------------------------------
# Custom Exceptions
# -------------------------------------------------------------------------

class OtpTokenError(ValueError):
    """Raised when an OTP token cannot be used."""


class OtpTokenExpiredError(OtpTokenError):
    """Raised when an OTP token is expired."""


# -------------------------------------------------------------------------
# Internal Helpers (DRY)
# -------------------------------------------------------------------------

def _get_signer(purpose: str) -> TimestampSigner:
    """
    Return a TimestampSigner instance for the given purpose.

    The salt is unique per purpose, preventing token reuse across contexts.
    """
    return TimestampSigner(salt=f"otp-token-{purpose}")


def _get_token_max_age() -> int:
    """Return the token validity duration in seconds from settings."""
    minutes = getattr(settings, "OTP_VALID_MINUTES", DEFAULT_TOKEN_VALID_MINUTES)
    return minutes * 60


def _get_cooldown_timeout() -> int:
    """Return the cooldown duration in seconds from settings."""
    return getattr(settings, "OTP_REQUEST_COOLDOWN_SECONDS", DEFAULT_COOLDOWN_SECONDS)


# -------------------------------------------------------------------------
# Public OTP Code Functions
# -------------------------------------------------------------------------

def generate_otp_code(length: int = DEFAULT_OTP_LENGTH) -> str:
    """
    Generate a cryptographically secure numeric OTP code.

    Args:
        length: Number of digits (minimum 4, enforced automatically).

    Returns:
        A string of digits with exactly `length` characters.
    """
    # Ensure minimum length for security
    length = max(length, MIN_OTP_LENGTH)
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"


def hash_otp_code(code: str) -> str:
    """Hash a plaintext OTP using Django's password hasher."""
    return make_password(code)


def verify_otp_code(code: str, hashed: str) -> bool:
    """Check if a plaintext OTP matches its stored hash."""
    if not hashed:
        return False
    return check_password(code, hashed)


# -------------------------------------------------------------------------
# Signed Token Functions (for email links, etc.)
# -------------------------------------------------------------------------

def create_otp_token(otp_id: str, user_id: str, purpose: str) -> str:
    """
    Create a signed, timestamped token.

    The token contains otp_id, user_id, and purpose, separated by TOKEN_SEPARATOR.
    It is signed and timestamped to prevent tampering and allow expiration.

    Args:
        otp_id: The ID of the OTP record.
        user_id: The ID of the user.
        purpose: The context (e.g., 'email_verification').

    Returns:
        A signed token string safe for use in URLs.
    """
    payload = TOKEN_SEPARATOR.join([str(otp_id), str(user_id), purpose])
    signer = _get_signer(purpose)
    return signer.sign(payload)


def validate_otp_token(signed_token: str, purpose: str) -> dict[str, str]:
    """
    Validate a signed, timestamped token.

    Args:
        signed_token: The token to validate.
        purpose: The expected purpose (must match the one used at creation).

    Returns:
        A dict with keys: otp_id, user_id, purpose.

    Raises:
        OtpTokenExpiredError: If the token has expired.
        OtpTokenError: If the token is malformed, tampered, or has a mismatched purpose.
    """
    signer = _get_signer(purpose)
    max_age = _get_token_max_age()

    try:
        payload = signer.unsign(signed_token, max_age=max_age)
    except SignatureExpired as err:
        raise OtpTokenExpiredError(_("The verification code has expired.")) from err
    except BadSignature as err:
        raise OtpTokenError(_("The verification link is invalid.")) from err

    parts = payload.split(TOKEN_SEPARATOR)
    if len(parts) != 3:  # noqa: PLR2004
        raise OtpTokenError(_("The verification link is invalid."))

    otp_id, user_id, embedded_purpose = parts
    if embedded_purpose != purpose:
        raise OtpTokenError(_("This code does not match the requested operation."))

    return {"otp_id": otp_id, "user_id": user_id, "purpose": purpose}


# -------------------------------------------------------------------------
# Rate Limiting (Cooldown)
# -------------------------------------------------------------------------

def _cooldown_key(user_id: str, purpose: str) -> str:
    """Generate a cache key for cooldown tracking."""
    return f"otp_cooldown:{purpose}:{user_id}"


def check_cooldown(user_id: str, purpose: str) -> tuple[bool, int]:
    """
    Check if the user is currently in cooldown.

    Args:
        user_id: The user identifier.
        purpose: The operation context.

    Returns:
        A tuple (is_blocked, remaining_seconds).
        If not blocked, remaining_seconds is 0.
    """
    key = _cooldown_key(user_id, purpose)

    # Some cache backends (e.g., locmem) do not support .ttl()
    remaining = cache.ttl(key) if hasattr(cache, "ttl") else None

    if remaining is not None and remaining > 0:
        return True, remaining

    # Fallback: if the key exists but we cannot get TTL, assume full cooldown time
    if cache.get(key):
        return True, _get_cooldown_timeout()

    return False, 0

def set_cooldown(user_id: str, purpose: str) -> None:
    """
    Activate a cooldown for the user for the given purpose.

    The duration is taken from settings (or default).
    """
    timeout = _get_cooldown_timeout()
    cache.set(_cooldown_key(user_id, purpose), value=True, timeout=timeout)

