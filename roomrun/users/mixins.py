from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


class RedirectToNextOrReferrerMixin:
    """
    Redirect users to a safe ``next`` URL, then an internal referrer, or home.
    """

    fallback_url = "home"

    def is_safe_url(self, url):
        """Return whether a URL is local and safe to redirect to."""
        return url_has_allowed_host_and_scheme(
            url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        )

    def get_redirect_url(self):
        """Return the highest-priority safe redirect URL."""
        next_url = self.request.GET.get("next")
        if next_url and self.is_safe_url(next_url):
            return next_url

        referrer = self.request.META.get("HTTP_REFERER")
        if referrer and self.is_safe_url(referrer):
            return referrer

        return reverse(self.fallback_url)

    def dispatch(self, request, *args, **kwargs):
        """Redirect authenticated users away from anonymous-only screens."""
        if self.request.user.is_authenticated:
            return HttpResponseRedirect(self.get_redirect_url())
        return super().dispatch(request, *args, **kwargs)

    # FormView uses this method after a valid submission.
    def get_success_url(self):
        return self.get_redirect_url()
