from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


class RedirectToNextOrReferrerMixin:
    """
    Redirect users to a safe ``next`` URL, then an internal referrer, or home.

    This mixin is intended for views that should only be accessible to anonymous
    users (e.g., login, signup). Authenticated users are redirected away.
    """

    # Can be overridden as a class attribute or via a method.
    fallback_url: str = "home"

    def is_safe_url(self, url: str) -> bool:
        """Return whether a URL is local and safe to redirect to."""
        return url_has_allowed_host_and_scheme(
            url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        )

    def get_fallback_url(self) -> str:
        """Return the fallback URL when no safe redirect is found."""
        return reverse(self.fallback_url)

    def get_redirect_url(self) -> str:
        """
        Return the highest-priority safe redirect URL.

        Priority:
        1. 'next' parameter from GET or POST.
        2. HTTP_REFERER header (if safe).
        3. fallback_url.
        """
        # Check GET first, then POST.
        next_url = self.request.GET.get("next") or self.request.POST.get("next")
        if next_url and self.is_safe_url(next_url):
            return next_url

        referrer = self.request.META.get("HTTP_REFERER")
        if referrer and self.is_safe_url(referrer):
            return referrer

        return self.get_fallback_url()

    def dispatch(self, request, *args, **kwargs):
        """Redirect authenticated users away from anonymous-only screens."""
        if request.user.is_authenticated:
            return HttpResponseRedirect(self.get_redirect_url())
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self) -> str:
        """
        Override for FormView to redirect after a valid form submission.
        """
        return self.get_redirect_url()
