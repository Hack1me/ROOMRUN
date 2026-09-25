from django.urls import path
from rentals.views.document_views import LeaseDocumentPreviewView
from rentals.views.document_views import LeasePDFView
from rentals.views.land_ren_views import LandlordContractExtensionDecisionView
from rentals.views.land_ren_views import LandlordRentalApplicationDetailView
from rentals.views.land_ren_views import LandlordRentalApplicationListView
from rentals.views.land_ren_views import LandlordRentalContractCreateView
from rentals.views.land_ren_views import LandlordRentalContractDetailView
from rentals.views.land_ren_views import LandlordRentalContractListView
from rentals.views.land_ren_views import RentalApplicationApproveView
from rentals.views.land_ren_views import RentalApplicationRejectView
from rentals.views.land_ren_views import TenantSearchView
from rentals.views.ten_ren_views import RentalApplicationCreateView
from rentals.views.ten_ren_views import RentalApplicationDetailView
from rentals.views.ten_ren_views import RentalApplicationListView
from rentals.views.ten_ren_views import RentalContractTerminateView
from rentals.views.ten_ren_views import TenantContractExtensionRequestView
from rentals.views.ten_ren_views import TenantLeaseDetailView
from rentals.views.ten_ren_views import TenantRentalContractSignView

app_name = "rentals"

urlpatterns = [
    path(
        "contracts/<slug:pk>/document/",
        LeaseDocumentPreviewView.as_view(),
        name="lease-document",
    ),
    path(
        "contracts/<slug:pk>/document/pdf/",
        LeasePDFView.as_view(),
        name="lease-pdf",
    ),
    path(
        "applications/",
        RentalApplicationListView.as_view(),
        name="rental-application-list",
    ),
    path(
        "applications/create/",
        RentalApplicationCreateView.as_view(),
        name="rental-application-create",
    ),
    path(
        "applications/<slug:pk>/",
        RentalApplicationDetailView.as_view(),
        name="rental-application-detail",
    ),
    path(
        "contracts/<slug:pk>/sign/",
        TenantRentalContractSignView.as_view(),
        name="tenant-rental-contract-sign",
    ),
    path(
        "contracts/<slug:pk>/terminate/",
        RentalContractTerminateView.as_view(),
        name="rental-contract-terminate",
    ),
    path(
        "contracts/<slug:pk>/extensions/request/",
        TenantContractExtensionRequestView.as_view(),
        name="tenant-extension-request",
    ),
    path(
        "mylease/",
        TenantLeaseDetailView.as_view(),
        name="tenant-lease-detail",
    ),
]

urlpatterns += [
    path(
        "landlord/applications/",
        LandlordRentalApplicationListView.as_view(),
        name="landlord-rental-application-list",
    ),

    path(
        "landlord/applications/<slug:pk>/",
        LandlordRentalApplicationDetailView.as_view(),
        name="landlord-rental-application-detail",
    ),

    path(
        "landlord/applications/<slug:pk>/approve/",
        RentalApplicationApproveView.as_view(),
        name="rental-application-approve",
    ),

    path(
        "landlord/applications/<slug:pk>/reject/",
        RentalApplicationRejectView.as_view(),
        name="rental-application-reject",
    ),
    path(
        "landlord/contracts/create/",
        LandlordRentalContractCreateView.as_view(),
        name="landlord-rental-contract-create",
    ),
    path(
        "landlord/contracts/",
        LandlordRentalContractListView.as_view(),
        name="landlord-rental-contract-list",
    ),
    path(
        "landlord/contracts/<slug:pk>/",
        LandlordRentalContractDetailView.as_view(),
        name="landlord-rental-contract-detail",
    ),
    path(
        "landlord/extensions/<slug:pk>/decision/",
        LandlordContractExtensionDecisionView.as_view(),
        name="landlord-extension-decision",
    ),
    path(
        "landlord/tenants/search/",
        TenantSearchView.as_view(),
        name="landlord-tenant-search",
    ),
]
