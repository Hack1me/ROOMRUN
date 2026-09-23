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
]
