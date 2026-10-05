from django.urls import path
from properties.views.building_view import BuildingCreateView
from properties.views.building_view import BuildingDetailView
from properties.views.building_view import BuildingUpdateView
from properties.views.property_img_view import PropertyImageCreateView
from properties.views.property_img_view import PropertyImageDeleteView
from properties.views.property_img_view import PropertyImagePrimaryView
from properties.views.property_img_view import PropertyImageUpdateView
from properties.views.property_view import PropertyConfigurationView
from properties.views.property_view import PropertyCreateView
from properties.views.property_view import PropertyDeleteView
from properties.views.property_view import PropertyDetailView
from properties.views.property_view import PropertyImagesView
from properties.views.property_view import PropertyListView
from properties.views.property_view import PropertyUpdateView
from properties.views.unit_img_view import UnitImageCreateView
from properties.views.unit_img_view import UnitImageDeleteView
from properties.views.unit_img_view import UnitImagePrimaryView
from properties.views.unit_view import LandlordUnitOverviewView
from properties.views.unit_view import UnitCreateView
from properties.views.unit_view import UnitDeleteView
from properties.views.unit_view import UnitDetailView
from properties.views.unit_view import UnitImagesView
from properties.views.unit_view import UnitListView
from properties.views.unit_view import UnitUpdateView

app_name = "properties"

urlpatterns = [
    path(
        "",
        PropertyListView.as_view(),
        name="property-list",
    ),
    path(
        "create/",
        PropertyCreateView.as_view(),
        name="property-create",
    ),
    path(
        "units/",
        LandlordUnitOverviewView.as_view(),
        name="landlord-unit-list",
    ),
    path(
        "<slug:pk>/",
        PropertyDetailView.as_view(),
        name="property-detail",
    ),
    path(
        "<slug:pk>/edit/",
        PropertyUpdateView.as_view(),
        name="property-edit",
    ),
    path(
        "<slug:pk>/configure/",
        PropertyConfigurationView.as_view(),
        name="property-configure",
    ),
    path(
        "<slug:pk>/images/",
        PropertyImagesView.as_view(),
        name="property-images",
    ),
    path(
        "<slug:pk>/delete/",
        PropertyDeleteView.as_view(),
        name="property-delete",
    ),
]

urlpatterns += [
    path(
        "<slug:property_id>/images/add/",
        PropertyImageCreateView.as_view(),
        name="property-image-add",
    ),
    path(
        "images/<slug:image_id>/primary/",
        PropertyImagePrimaryView.as_view(),
        name="property-image-primary",
    ),
    path(
        "images/<slug:image_id>/edit/",
        PropertyImageUpdateView.as_view(),
        name="property-image-edit",
    ),
    path(
        "images/<slug:image_id>/delete/",
        PropertyImageDeleteView.as_view(),
        name="property-image-delete",
    ),
]

urlpatterns += [
    path(
        "buildings/<slug:pk>/",
        BuildingDetailView.as_view(),
        name="building-detail",
    ),
    path(
        "buildings/<slug:pk>/edit/",
        BuildingUpdateView.as_view(),
        name="building-edit",
    ),
    path(
        "<slug:property_id>/buildings/create/",
        BuildingCreateView.as_view(),
        name="property-buildings-create",
    ),
    path(
        "<slug:property_id>/buildings/<slug:building_id>/units/",
        UnitListView.as_view(),
        name="unit-list",
    ),
    path(
        "<slug:property_id>/buildings/<slug:building_id>/units/create/",
        UnitCreateView.as_view(),
        name="unit-create",
    ),
    path(
        "units/<slug:pk>/",
        UnitDetailView.as_view(),
        name="unit-detail",
    ),
    path(
        "units/<slug:pk>/edit/",
        UnitUpdateView.as_view(),
        name="unit-edit",
    ),
    path(
        "units/<slug:pk>/delete/",
        UnitDeleteView.as_view(),
        name="unit-delete",
    ),
    path(
        "units/<slug:pk>/images/",
        UnitImagesView.as_view(),
        name="unit-images",
    ),
    path(
        "units/<slug:unit_id>/images/add/",
        UnitImageCreateView.as_view(),
        name="unit-image-add",
    ),
    path(
        "unit-images/<slug:image_id>/primary/",
        UnitImagePrimaryView.as_view(),
        name="unit-image-primary",
    ),
    path(
        "unit-images/<slug:image_id>/delete/",
        UnitImageDeleteView.as_view(),
        name="unit-image-delete",
    ),
]
