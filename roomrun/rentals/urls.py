from django.urls import path
from rentals.land_ren_views import LandlordRentalApplicationDetailView
from rentals.land_ren_views import LandlordRentalApplicationListView
from rentals.land_ren_views import RentalApplicationApproveView
from rentals.land_ren_views import RentalApplicationRejectView
from rentals.ten_ren_views import RentalApplicationCreateView
from rentals.ten_ren_views import RentalApplicationDetailView
from rentals.ten_ren_views import RentalApplicationListView

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
]