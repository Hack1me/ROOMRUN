from __future__ import annotations

import datetime
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from users.models import Otp
from users.tasks import send_otp_email_task
from utils.enums import OtpPurpose
from utils.otp import check_cooldown
from utils.otp import create_otp_token
from utils.otp import generate_otp_code
from utils.otp import hash_otp_code
from utils.otp import set_cooldown
from utils.otp import validate_otp_token


class OtpRateLimitError(ValueError):
    pass


class OtpVerificationError(ValueError):
    pass


class OtpService:
    @staticmethod
    def create(user, purpose: str) -> tuple[Otp, str]:
        limited, _remaining = check_cooldown(str(user.pk), purpose)
        if limited:
            raise OtpRateLimitError(_("Please wait before requesting another code."))

        validity = getattr(settings, "OTP_VALID_MINUTES", 10)
        raw_code = generate_otp_code()
        expiration_at = timezone.now() + datetime.timedelta(minutes=validity)

        with transaction.atomic():
            Otp.objects.filter(user=user, purpose=purpose, is_used=False).update(
                is_used=True
            )
            otp = Otp.objects.create(
                user=user,
                purpose=purpose,
                code_hash=hash_otp_code(raw_code),
                expiration_at=expiration_at,
            )
            set_cooldown(str(user.pk), purpose)

        otp._raw_code = raw_code  # noqa: SLF001
        token = create_otp_token(str(otp.pk), str(user.pk), purpose)
        return otp, token


class OtpEmailService:
    @staticmethod
    def send(user, otp: Otp, language: str | None = None) -> None:
        raw_code = getattr(otp, "_raw_code", None)
        if not raw_code:
            msg = "Raw OTP code is required."
            raise ValueError(msg)

        full_name = user.fu or user.email
        validity = getattr(settings, "OTP_VALID_MINUTES", 10)
        lang = language or getattr(user, "language", None) or settings.LANGUAGE_CODE

        transaction.on_commit(
            lambda: send_otp_email_task.delay(
                email=user.email,
                full_name=full_name,
                code=raw_code,
                validity=validity,
                language=lang,
            ),
        )


class OtpVerifyService:
    @staticmethod
    def _resolve_otp(token: str, purpose: str) -> Otp:
        token_data = validate_otp_token(token, purpose)
        try:
            return (
                Otp.objects.select_for_update()
                .select_related("user")
                .get(
                    pk=token_data["otp_id"],
                    user_id=token_data["user_id"],
                    purpose=purpose,
                )
            )
        except Otp.DoesNotExist as err:
            raise OtpVerificationError(
                _("This verification code could not be found.")
            ) from err

    @staticmethod
    def verify(token: str, code: str, purpose: str) -> Otp:
        with transaction.atomic():
            otp = OtpVerifyService._resolve_otp(token, purpose)
            if otp.is_used or otp.is_expired():
                raise OtpVerificationError(
                    _("This code has expired. Request a new one.")
                )
            if not otp.can_attempt():
                raise OtpVerificationError(_("Too many attempts. Request a new code."))

            otp.increment_attempts()
            if not otp.is_valid_code(code):
                raise OtpVerificationError(_("The code you entered is incorrect."))

            otp.mark_verified()
            if purpose in {OtpPurpose.SIGNUP, OtpPurpose.LOGIN}:
                user = otp.user
                user.email_verified = True
                user.save(update_fields=["email_verified"])
            return otp


class PasswordResetTokenService:
    timeout = getattr(settings, "RESET_TOKEN_TIMEOUT", 15) * 60

    @staticmethod
    def generate(user) -> str:
        token = str(uuid.uuid4())
        cache.set(
            f"password_reset_token:{token}",
            str(user.pk),
            timeout=PasswordResetTokenService.timeout,
        )
        return token

    @staticmethod
    def get_user_id(token: str) -> str | None:
        if not token:
            return None
        return cache.get(f"password_reset_token:{token}")

    @staticmethod
    def delete(token: str) -> None:
        cache.delete(f"password_reset_token:{token}")
