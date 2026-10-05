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
        "cleaning/<slug:pk>/",
        views.LandlordCleaningScheduleDetailView.as_view(),
        name="cleaning-detail",
    ),
    path(
        "cleaning/<slug:pk>/edit/",
        views.LandlordCleaningScheduleUpdateView.as_view(),
        name="cleaning-edit",
    ),
    path(
        "cleaning/<slug:pk>/status/",
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
        "visitors/invitations/<slug:pk>/cancel/",
        views.VisitorInvitationCancelView.as_view(),
        name="visitor-invitation-cancel",
    ),
    path(
        "guard/visitors/", views.GuardVisitorListView.as_view(), name="guard-visitors"
    ),
    path(
        "guard/visitors/check-in/",
        views.GuardCheckInView.as_view(),
        name="guard-visitor-check-in",
    ),
    path(
        "guard/visitors/scan/",
        views.GuardVisitorQRScanView.as_view(),
        name="guard-visitor-qr-scan",
    ),
    path(
        "guard/visitors/history/",
        views.GuardVisitorHistoryView.as_view(),
        name="guard-visitor-history",
    ),
    path(
        "guard/visitors/<slug:pk>/status/",
        views.GuardVisitorStatusView.as_view(),
        name="guard-visitor-status",
    ),
]
