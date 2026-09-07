from django.urls import path
from django.views.generic import TemplateView
from users.views.dashboard import DashboardView
from users.views.dashboard import GuardDashboardView
from users.views.dashboard import LandlordDashboardView
from users.views.dashboard import MaintenanceDashboardView
from users.views.dashboard import TenantDashboardView

app_name = "dashboard"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("landlord/", LandlordDashboardView.as_view(), name="landlord"),
    path("tenant/", TenantDashboardView.as_view(), name="tenant"),
    path("maintenance/", MaintenanceDashboardView.as_view(), name="maintenance"),
    path("guard/", GuardDashboardView.as_view(), name="guard"),
    path(
        "user/",
        TemplateView.as_view(template_name="dashboard/pages/user.html"),
        name="user",
    ),
]
