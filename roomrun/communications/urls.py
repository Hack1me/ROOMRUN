from communications import views
from django.urls import path

app_name = "communications"

urlpatterns = [
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
]
