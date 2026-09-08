from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from users.services import OtpEmailService


class NormalizedEmailMixin:
    def clean_email(self):
        return self.cleaned_data["email"].lower().strip()


class PasswordConfirmMixin:
    password1_field = "password1"
    password2_field = "password2"

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get(self.password1_field)
        password2 = cleaned_data.get(self.password2_field)
        if password1 and password2 and password1 != password2:
            self.add_error(self.password2_field, _("The passwords do not match."))
        if password1:
            try:
                
                validate_password(password1)
            except Exception as error:
                self.add_error(self.password1_field, error)
        return cleaned_data


class RedirectToNextOrReferrerMixin:
    """
    Redirect users to a safe ``next`` URL, then an internal referrer, or home.

    This mixin is intended for views that should only be accessible to anonymous
    users (e.g., login, signup). Authenticated users are redirected away.
    """

    fallback_url: str = "home"

    def is_safe_url(self, url: str) -> bool:
        return url_has_allowed_host_and_scheme(
            url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        )

    def get_fallback_url(self) -> str:
        return reverse(self.fallback_url)

    def get_redirect_url(self) -> str:
        next_url = self.request.GET.get("next") or self.request.POST.get("next")
        if next_url and self.is_safe_url(next_url):
            return next_url
        referrer = self.request.META.get("HTTP_REFERER")
        if referrer and self.is_safe_url(referrer):
            return referrer
        return self.get_fallback_url()

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return HttpResponseRedirect(self.get_redirect_url())
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self) -> str:
        return self.get_redirect_url()


class DashboardProfileMixin:
    profile_attr: str | None = None
    error_message: str | None = None
    service_class = None
    fallback_url: str = "dashboard:dashboard"

    def dispatch(self, request, *args, **kwargs):
        if self.profile_attr and not self._has_profile(request.user):
            messages.error(request, self.error_message or _("Access denied."))
            return redirect(self.fallback_url)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.service_class:
            context.update(self.service_class.get_context(self.request.user))
        return context

    def _has_profile(self, user) -> bool:
        parts = self.profile_attr.split(".")
        current = user
        for part in parts:
            if not hasattr(current, part):
                return False
            current = getattr(current, part)
        return True


class OtpSessionKeyMixin:
    otp_session_prefix = "pending_otp_token"

    def otp_session_key(self, purpose: str) -> str:
        return f"{self.otp_session_prefix}:{purpose}"

    def set_otp_token(self, purpose: str, token: str) -> None:
        self.request.session[self.otp_session_key(purpose)] = token

    def pop_otp_token(self, purpose: str) -> None:
        self.request.session.pop(self.otp_session_key(purpose), None)


class OtpEmailMixin:
    def send_otp_email(self, user, otp):
        return OtpEmailService.send(
            user, otp, language=get_language_from_request(self.request)
        )
