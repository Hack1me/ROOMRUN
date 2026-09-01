from django.contrib import messages
from django.db import IntegrityError
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from users.forms import SignupForm
from users.services import OtpEmailService
from users.services import OtpRateLimitError
from users.services import OtpService
from utils.enums import OtpPurpose


class SignupView(FormView):
    template_name = "home/pages/auth/signup.html"
    form_class = SignupForm

    def get_success_url(self):
        return self.request.GET.get("next") or "users:verify_otp"

    def form_valid(self, form):
        try:
            with transaction.atomic():
                user = form.save()
                otp, token = OtpService.create(user, OtpPurpose.SIGNUP)
                OtpEmailService.send(
                    user, otp, language=get_language_from_request(self.request)
                )
        except IntegrityError:
            form.add_error(
                "email", _("An account already exists with this email address.")
            )
            messages.error(self.request, _("Please correct the sign-up details."))
            return self.form_invalid(form)
        except OtpRateLimitError as error:
            messages.warning(self.request, error)
            return self.form_invalid(form)

        self.request.session["pending_signup_token"] = token
        messages.success(
            self.request,
            _(
                "Your account has been created. Enter the code sent by email to activate it."
            ),
        )
        return redirect("users:verify_otp", purpose=OtpPurpose.SIGNUP, token=token)

    def form_invalid(self, form):
        messages.error(self.request, _("Please correct the sign-up details."))
        return super().form_invalid(form)
