"""Custom error handlers for the public ROOMRUN interface."""

from typing import TYPE_CHECKING

from django.shortcuts import render

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.http import HttpResponse


def bad_request(request: HttpRequest, exception: Exception) -> HttpResponse:
    """Render the custom HTTP 400 page."""
    return render(request, "errors/400.html", {"exception": exception}, status=400)


def permission_denied(request: HttpRequest, exception: Exception) -> HttpResponse:
    """Render the custom HTTP 403 page."""
    return render(request, "errors/403.html", {"exception": exception}, status=403)


def page_not_found(request: HttpRequest, exception: Exception) -> HttpResponse:
    """Render the custom HTTP 404 page."""
    return render(request, "errors/404.html", {"exception": exception}, status=404)


def server_error(request: HttpRequest) -> HttpResponse:
    """Render the custom HTTP 500 page without exposing exception details."""
    return render(request, "errors/500.html", status=500)


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    """Render the custom CSRF failure page without leaking the failure reason."""
    return render(request, "errors/403_csrf.html", status=403)
