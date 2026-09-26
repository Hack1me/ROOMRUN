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
        "notifications/delete-all/",
        views.NotificationDeleteAllView.as_view(),
        name="notification-delete-all",
    ),
    path(
        "notifications/<slug:pk>/open/",
        views.NotificationOpenView.as_view(),
        name="notification-open",
    ),
    path(
        "notifications/<slug:pk>/",
        views.NotificationDetailView.as_view(),
        name="notification-detail",
    ),
    path(
        "notifications/<slug:pk>/delete/",
        views.NotificationDeleteView.as_view(),
        name="notification-delete",
    ),
    path(
        "notifications/<slug:pk>/toggle-read/",
        views.NotificationToggleReadView.as_view(),
        name="notification-toggle-read",
    ),
    path(
        "conversations/",
        views.ConversationListView.as_view(),
        name="conversation-list",
    ),
    path(
        "conversations/<slug:pk>/",
        views.ConversationDetailView.as_view(),
        name="conversation-detail",
    ),
    path(
        "conversations/start/",
        views.StartConversationView.as_view(),
        name="conversation-start",
    ),
    path(
        "conversations/<slug:pk>/delete/",
        views.ConversationDeleteView.as_view(),
        name="conversation-delete",
    ),
]
