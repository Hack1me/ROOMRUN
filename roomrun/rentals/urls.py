from django.urls import path
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

app_name = "rentals"

urlpatterns = [
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
        "applications/<uuid:pk>/",
        RentalApplicationDetailView.as_view(),
        name="rental-application-detail",
    ),
]

urlpatterns += [
    path(
        "landlord/applications/",
        LandlordRentalApplicationListView.as_view(),
        name="landlord-rental-application-list",
    ),

    path(
        "landlord/applications/<uuid:pk>/",
        LandlordRentalApplicationDetailView.as_view(),
        name="landlord-rental-application-detail",
    ),

    path(
        "landlord/applications/<uuid:pk>/approve/",
        RentalApplicationApproveView.as_view(),
        name="rental-application-approve",
    ),

    path(
        "landlord/applications/<uuid:pk>/reject/",
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
        "landlord/contracts/<uuid:pk>/",
        LandlordRentalContractDetailView.as_view(),
        name="landlord-rental-contract-detail",
    ),
    path(
        "landlord/tenants/search/",
        TenantSearchView.as_view(),
        name="landlord-tenant-search",
    ),
]
