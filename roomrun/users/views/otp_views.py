from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView
from users.forms import OtpVerificationForm
from users.mixins import RedirectToNextOrReferrerMixin
from users.services import OtpEmailService
from users.services import OtpRateLimitError
from users.services import OtpService
from users.services import OtpVerificationError
from users.services import OtpVerifyService
from users.services import PasswordResetTokenService
from utils.enums import OtpPurpose


class VerifyOtpView(RedirectToNextOrReferrerMixin, FormView):
    template_name = "home/pages/auth/verify_otp.html"
    form_class = OtpVerificationForm

    def dispatch(self, request, *args, **kwargs):
        self.purpose = kwargs["purpose"]
        self.token = kwargs["token"]
        if self.purpose not in {
            OtpPurpose.SIGNUP,
            OtpPurpose.LOGIN,
            OtpPurpose.PASSWORD_RESET,
        }:
            messages.error(request, _("This verification is not available."))
            return redirect("users:signin")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {"token": self.token}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["purpose"] = self.purpose
        context["token"] = self.token
        context["title"] = _("Verify your account")
        context["subtitle"] = _("Enter the six-digit code sent to your email address.")
        if self.purpose == OtpPurpose.PASSWORD_RESET:
            context["title"] = _("Verify the reset code")
            context["subtitle"] = _("Enter the code sent to create a new password.")
        return context

    def form_valid(self, form):
        try:
            otp = OtpVerifyService.verify(
                token=form.cleaned_data["token"],
                code=form.cleaned_data["code"],
                purpose=self.purpose,
            )
        except OtpVerificationError as error:
            messages.error(self.request, error)
            return self.form_invalid(form)
        except ValueError as error:
            messages.error(self.request, str(error))
            return self.form_invalid(form)

        user = otp.user
        if self.purpose == OtpPurpose.PASSWORD_RESET:
            reset_token = PasswordResetTokenService.generate(user)
            messages.success(
                self.request, _("Code verified. You can now create a new password.")
            )
            return redirect("users:reset_password", token=reset_token)

        login(self.request, user)
        messages.success(self.request, _("Your account is now verified."))
        return redirect("users:redirect")

    def form_invalid(self, form):
        messages.error(self.request, _("Please check the verification code."))
        return super().form_invalid(form)


class ResendOtpView(RedirectToNextOrReferrerMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        purpose = kwargs["purpose"]
        token = kwargs["token"]
        try:
            with transaction.atomic():
                otp = OtpVerifyService._resolve_otp(token, purpose)  # noqa: SLF001
                new_otp, new_token = OtpService.create(otp.user, purpose)

        except (OtpVerificationError, OtpRateLimitError, ValueError) as error:
            messages.error(request, error)
            return redirect("users:verify_otp", purpose=purpose, token=token)
        try:
            OtpEmailService.send(
                otp.user, new_otp, language=get_language_from_request(request)
            )
        except Exception:  # noqa: BLE001
            messages.warning(
                self.request,
                _("Server Error. Request a new code on the next page.")
            )
        messages.success(request, _("A new verification code has been sent."))
        return redirect("users:verify_otp", purpose=purpose, token=new_token)
