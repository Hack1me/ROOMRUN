import logging

from django.contrib import messages
from django.db import IntegrityError
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from users.forms import SignupForm
from users.mixins import OtpEmailMixin
from users.mixins import OtpSessionKeyMixin
from users.mixins import RedirectToNextOrReferrerMixin
from users.models import Landlord
from users.models import Tenant
from users.services import OtpRateLimitError
from users.services import OtpService
from utils.enums import OtpPurpose

logger = logging.getLogger(__name__)


class SignupView(OtpEmailMixin, OtpSessionKeyMixin, RedirectToNextOrReferrerMixin, FormView):
    template_name = "home/pages/auth/signup.html"
    form_class = SignupForm

    def form_valid(self, form):
        role = form.cleaned_data.get("role")
        try:
            with transaction.atomic():
                user = form.save()
                if role == "landlord":
                    Landlord.objects.create(user=user)
                elif role == "tenant":
                    Tenant.objects.create(user=user)
                otp, token = OtpService.create(user, OtpPurpose.SIGNUP)
        except IntegrityError:
            form.add_error(
                "email", _("An account already exists with this email address.")
            )
            messages.error(self.request, _("Please correct the sign-up details."))
            return self.form_invalid(form)
        except OtpRateLimitError as error:
            messages.warning(self.request, error)
            return self.form_invalid(form)

        try:
            self.send_otp_email(user, otp)
        except Exception:
            logger.exception("Unable to send the sign-up verification email")
            messages.warning(
                self.request, _("Server Error. Request a new code on the next page.")
            )

        self.set_otp_token(OtpPurpose.SIGNUP, token)
        messages.success(
            self.request,
            _(
                "Your account has been created. Enter the code sent by email to activate it."  # noqa: E501
            ),
        )
        return redirect("users:verify_otp", purpose=OtpPurpose.SIGNUP)

    def form_invalid(self, form):
        messages.error(self.request, _("Please correct the sign-up details."))
        return super().form_invalid(form)
