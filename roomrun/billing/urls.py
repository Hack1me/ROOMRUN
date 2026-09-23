from billing.views import CamPayWebhookView
from django.urls import path

app_name = "billing"

urlpatterns = [
    path(
        "webhook/campay/",
        CamPayWebhookView.as_view(),
        name="campay-webhook",
    ),

    # Autres routes (à ajouter plus tard) :
    # path("payments/", PaymentListView.as_view(), name="payment-list"),  # noqa: ERA001
    # path("payments/<uuid:pk>/", PaymentDetailView.as_view(), name="payment-detail"),  # noqa: ERA001
    # path("payments/<uuid:pk>/initiate/", PaymentInitiateView.as_view(), name="payment-initiate"),  # noqa: ERA001
]
