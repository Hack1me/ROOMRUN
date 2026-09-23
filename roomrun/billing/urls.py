from billing.views import CamPayWebhookView
from billing.views import TenantChargeListView
from billing.views import TenantPaymentInitiateView
from billing.views import TenantPaymentSynchronizeView
from django.urls import path

app_name = "billing"

urlpatterns = [
    path("charges/", TenantChargeListView.as_view(), name="tenant-charge-list"),
    path(
        "charges/<uuid:pk>/pay/",
        TenantPaymentInitiateView.as_view(),
        name="tenant-payment-initiate",
    ),
    path(
        "payments/<uuid:pk>/sync/",
        TenantPaymentSynchronizeView.as_view(),
        name="tenant-payment-sync",
    ),
    path(
        "webhook/campay/",
        CamPayWebhookView.as_view(),
        name="campay-webhook",
    ),
    # Autres routes (à ajouter plus tard) :
    # path("payments/", PaymentListView.as_view(), name="payment-list"),  # noqa: ERA001
    # path("payments/<uuid:pk>/", PaymentDetailView.as_view(), name="payment-detail"),  # noqa: E501, ERA001
    # path("payments/<uuid:pk>/initiate/", PaymentInitiateView.as_view(), name="payment-initiate"),  # noqa: E501, ERA001
]
