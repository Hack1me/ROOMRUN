from communications import views
from django.urls import path

app_name = "communications"

urlpatterns = [
    path(
        "notifications/", views.NotificationListView.as_view(), name="notification-list"
    ),
    path(
        "notifications/read-all/",
        views.NotificationMarkAllReadView.as_view(),
        name="notification-read-all",
    ),
    path(
        "notifications/<uuid:pk>/",
        views.NotificationDetailView.as_view(),
        name="notification-detail",
    ),
    path(
        "notifications/<uuid:pk>/toggle-read/",
        views.NotificationToggleReadView.as_view(),
        name="notification-toggle-read",
    ),
    path(
        "conversations/",
        views.ConversationListView.as_view(),
        name="conversation-list",
    ),
    path(
        "conversations/<uuid:pk>/",
        views.ConversationDetailView.as_view(),
        name="conversation-detail",
    ),
    path(
        "conversations/start/",
        views.StartConversationView.as_view(),
        name="conversation-start",
    ),
    path(
        "conversations/<uuid:pk>/delete/",
        views.ConversationDeleteView.as_view(),
        name="conversation-delete",
    ),
]
