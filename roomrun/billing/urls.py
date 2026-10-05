from billing.views import CamPayWebhookView
from billing.views import DigiPayWebhookView
from billing.views import LandlordChargeCreateView
from billing.views import LandlordChargeListView
from billing.views import TenantChargeListView
from billing.views import TenantContractPaymentView
from billing.views import TenantPaymentInitiateView
from billing.views import TenantPaymentSynchronizeView
from billing.wallet_views import LandlordWalletView
from django.urls import path

app_name = "billing"

urlpatterns = [
    path(
        "landlord/charges/",
        LandlordChargeListView.as_view(),
        name="landlord-charge-list",
    ),
    path(
        "landlord/charges/new/",
        LandlordChargeCreateView.as_view(),
        name="landlord-charge-create",
    ),
    path("landlord/wallet/", LandlordWalletView.as_view(), name="landlord-wallet"),
    path("charges/", TenantChargeListView.as_view(), name="tenant-charge-list"),
    path(
        "contracts/<slug:pk>/pay/",
        TenantContractPaymentView.as_view(),
        name="tenant-contract-payment",
    ),
    path(
        "charges/<slug:pk>/pay/",
        TenantPaymentInitiateView.as_view(),
        name="tenant-payment-initiate",
    ),
    path(
        "payments/<slug:pk>/sync/",
        TenantPaymentSynchronizeView.as_view(),
        name="tenant-payment-sync",
    ),
    path(
        "webhook/campay/",
        CamPayWebhookView.as_view(),
        name="campay-webhook",
    ),
    path(
        "webhook/digipay/",
        DigiPayWebhookView.as_view(),
        name="digipay-webhook",
    ),
    # Autres routes (à ajouter plus tard) :
    # path("payments/", PaymentListView.as_view(), name="payment-list"),  # noqa: ERA001
    # path("payments/<slug:pk>/", PaymentDetailView.as_view(), name="payment-detail"),  # noqa: E501, ERA001
    # path("payments/<slug:pk>/initiate/", PaymentInitiateView.as_view(), name="payment-initiate"),  # noqa: E501, ERA001
]
