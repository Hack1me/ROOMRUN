from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include
from django.urls import path
from django.views import defaults as default_views
from django.views.generic import TemplateView
from django.views.i18n import JavaScriptCatalog
from drf_spectacular.views import SpectacularAPIView
from drf_spectacular.views import SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token

handler400 = "core.error_views.bad_request"
handler403 = "core.error_views.permission_denied"
handler404 = "core.error_views.page_not_found"
handler500 = "core.error_views.server_error"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
]
urlpatterns += i18n_patterns(
    path("",
        TemplateView.as_view(template_name="dashboard/pages/home.html"),
        name="home",
        ),
    path(
        "about/",
        TemplateView.as_view(template_name="dashboard/pages/about.html"),
        name="about",
    ),
    path(
        "dashboard/",
        include("users.urls.dashboard_urls", namespace="dashboard"),
    ),
    path(
        "users/",
        include("users.urls.users_urls", namespace="users"),
    ),
    path(
        "properties/",
        include("properties.urls", namespace="properties"),
    ),
    path(
        "rentals/",
        include("rentals.urls", namespace="rentals"),
    ),
    path(
        "billing/",
        include("billing.urls", namespace="billing"),
    ),
    path(
        "communications/",
        include("communications.urls", namespace="communications"),
    ),
    path(
        "maintenance/",
        include("maintenance.urls", namespace="maintenance"),
    ),
    path(
        "operations/",
        include("operations.urls", namespace="operations"),
    ),
    path(
        "chaining/",
        include("smart_selects.urls"),
    ),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
)
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()

urlpatterns += [
    path("jsi18n/", JavaScriptCatalog.as_view(), name="jsi18n"),
    path("api/", include("config.api_router")),
    path("api/auth-token/", obtain_auth_token, name="obtain_auth_token"),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
]

if settings.DEBUG:
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
            *urlpatterns,
        ]
