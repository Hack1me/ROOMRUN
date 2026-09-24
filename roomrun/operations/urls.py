from django.urls import path
from operations import views

app_name = "operations"

urlpatterns = [
    path(
        "cleaning/",
        views.LandlordCleaningScheduleListView.as_view(),
        name="cleaning-list",
    ),
    path(
        "cleaning/new/",
        views.LandlordCleaningScheduleCreateView.as_view(),
        name="cleaning-create",
    ),
    path(
        "cleaning/<uuid:pk>/",
        views.LandlordCleaningScheduleDetailView.as_view(),
        name="cleaning-detail",
    ),
    path(
        "cleaning/<uuid:pk>/edit/",
        views.LandlordCleaningScheduleUpdateView.as_view(),
        name="cleaning-edit",
    ),
    path(
        "cleaning/<uuid:pk>/status/",
        views.LandlordCleaningStatusView.as_view(),
        name="cleaning-status",
    ),
    path(
        "my-cleaning-schedule/",
        views.TenantCleaningScheduleListView.as_view(),
        name="tenant-cleaning-list",
    ),
    path(
        "visitors/invitations/",
        views.VisitorInvitationView.as_view(),
        name="visitor-invitations",
    ),
    path(
        "visitors/invitations/<uuid:pk>/cancel/",
        views.VisitorInvitationCancelView.as_view(),
        name="visitor-invitation-cancel",
    ),
    path(
        "guard/visitors/", views.GuardVisitorListView.as_view(), name="guard-visitors"
    ),
    path(
        "guard/visitors/<uuid:pk>/status/",
        views.GuardVisitorStatusView.as_view(),
        name="guard-visitor-status",
    ),
]
