from django.urls import path
from django.views.generic import TemplateView
from users.views.dashboard import DashboardView
from users.views.dashboard import GuardDashboardView
from users.views.dashboard import LandlordDashboardView
from users.views.dashboard import MaintenanceDashboardView
from users.views.dashboard import TenantDashboardView
from users.views.emp_views import EmployeeListView
from users.views.ten_views import TenantListView
from users.views.invitation_views import LandlordInvitationCancelView
from users.views.invitation_views import LandlordInvitationListView

app_name = "dashboard"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("landlord/", LandlordDashboardView.as_view(), name="landlord"),
    path("landlord/tenants/", TenantListView.as_view(), name="tenant-list"),
    path("tenant/", TenantDashboardView.as_view(), name="tenant"),
    path("landlord/employees/", EmployeeListView.as_view(), name="employee-list"),
    path("maintenance/", MaintenanceDashboardView.as_view(), name="maintenance"),
    path("guard/", GuardDashboardView.as_view(), name="guard"),
    path("landlord/invitations/", LandlordInvitationListView.as_view(), name="invitation-list"),
    path("landlord/invitations/<uuid:pk>/cancel/", LandlordInvitationCancelView.as_view(), name="invitation-cancel"),
    path(
        "user/",
        TemplateView.as_view(template_name="dashboard/pages/user.html"),
        name="user",
    ),
]
