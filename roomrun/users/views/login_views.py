from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from django.views.generic import RedirectView
from users.forms import SigninForm
from users.services import OtpEmailService
from users.services import OtpRateLimitError
from users.services import OtpService
from utils.enums import OtpPurpose


class SigninView(FormView):
    template_name = "home/pages/auth/signin.html"
    form_class = SigninForm

    def get_success_url(self):
        return self.request.GET.get("next") or reverse(settings.LOGIN_REDIRECT_URL)

    def form_valid(self, form):
        user = form.user
        if not user.email_verified:
            try:
                otp, token = OtpService.create(user, OtpPurpose.LOGIN)
                OtpEmailService.send(
                    user, otp, language=get_language_from_request(self.request)
                )
            except OtpRateLimitError as error:
                messages.warning(self.request, error)
                return self.form_invalid(form)

            self.request.session["pending_login_token"] = token
            messages.info(self.request, _("A verification code has been sent to you."))
            return redirect("users:verify_otp", purpose=OtpPurpose.LOGIN, token=token)

        login(self.request, user)
        if not form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(0)
        messages.success(self.request, _("You are now signed in."))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("Please correct the sign-in details."))
        return super().form_invalid(form)


class UserRedirectView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse("home")


class UserLogoutView(LogoutView):
    next_page = "home"
