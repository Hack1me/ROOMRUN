from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from users.forms import ForgotPasswordForm
from users.forms import PasswordResetConfirmForm
from users.services import OtpEmailService
from users.services import OtpRateLimitError
from users.services import OtpService
from users.services import PasswordResetTokenService
from utils.enums import OtpPurpose

User = get_user_model()


class ForgotPasswordView(FormView):
    template_name = "home/pages/auth/forgot_password.html"
    form_class = ForgotPasswordForm

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        user = User.objects.filter(email__iexact=email).first()
        if user:
            try:
                otp, token = OtpService.create(user, OtpPurpose.PASSWORD_RESET)
                OtpEmailService.send(
                    user, otp, language=get_language_from_request(self.request)
                )
            except OtpRateLimitError:
                messages.info(
                    self.request,
                    _("If this address exists, a reset code has been sent."),
                )
                return redirect("users:signin")

            self.request.session["pending_otp_token:password_reset"] = token
            messages.info(self.request, _("A reset code has been sent to you."))
            return redirect(
                "users:verify_otp", purpose=OtpPurpose.PASSWORD_RESET
            )

        messages.info(
            self.request, _("If this address exists, a reset code has been sent.")
        )
        return redirect("users:signin")

    def form_invalid(self, form):
        messages.error(self.request, _("Enter a valid email address."))
        return super().form_invalid(form)


class ResetPasswordView(FormView):
    template_name = "home/pages/auth/reset_password.html"
    form_class = PasswordResetConfirmForm

    def dispatch(self, request, *args, **kwargs):
        self.token = request.session.get("pending_reset_token")
        if not self.token:
            messages.error(request, _("This password reset request has expired."))
            return redirect("users:forgot_password")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {"token": self.token}

    def form_valid(self, form):
        with transaction.atomic():
            user_id = PasswordResetTokenService.get_user_id(self.token)
            if not user_id:
                messages.error(self.request, _("This password reset request has expired."))
                return redirect("users:forgot_password")
            user = User.objects.select_for_update().get(pk=user_id)
            user.set_password(form.cleaned_data["password1"])
            user.save(update_fields=["password"])
            PasswordResetTokenService.delete(self.token)
        self.request.session.pop("pending_reset_token", None)
        messages.success(
            self.request, _("Your password has been updated. You can now sign in.")
        )
        return redirect("users:signin")

    def form_invalid(self, form):
        messages.error(self.request, _("Please correct the new password."))
        return super().form_invalid(form)
