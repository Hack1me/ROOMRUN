from django.urls import path
from maintenance import views

app_name = "maintenance"

urlpatterns = [
    path("requests/", views.TenantRequestListView.as_view(), name="request-list"),
    path(
        "landlord/requests/",
        views.LandlordRequestListView.as_view(),
        name="landlord-request-list",
    ),
    path(
        "landlord/requests/<uuid:pk>/",
        views.LandlordRequestDetailView.as_view(),
        name="landlord-request-detail",
    ),
    path(
        "requests/new/",
        views.TenantRequestCreateView.as_view(),
        name="request-create",
    ),
    path(
        "requests/<uuid:pk>/",
        views.TenantRequestDetailView.as_view(),
        name="request-detail",
    ),
    path(
        "requests/<uuid:pk>/cancel/",
        views.TenantRequestCancelView.as_view(),
        name="request-cancel",
    ),
    path(
        "attachments/<uuid:pk>/download/",
        views.AttachmentDownloadView.as_view(),
        name="attachment-download",
    ),
    path("work-queue/", views.AgentQueueView.as_view(), name="agent-queue"),
    path(
        "work-queue/<uuid:pk>/claim/",
        views.AgentClaimRequestView.as_view(),
        name="agent-claim",
    ),
    path("tasks/", views.AgentTaskListView.as_view(), name="task-list"),
    path("tasks/<uuid:pk>/", views.AgentTaskDetailView.as_view(), name="task-detail"),
]
