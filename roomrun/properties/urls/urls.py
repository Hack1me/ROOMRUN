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
from properties.views.unit_view import UnitCreateView
from properties.views.unit_view import UnitDeleteView
from properties.views.unit_view import UnitDetailView
from properties.views.unit_view import UnitListView
from properties.views.unit_view import UnitUpdateView
from properties.views.unit_view import UnitImagesView
from properties.views.unit_img_view import UnitImageCreateView
from properties.views.unit_img_view import UnitImageDeleteView
from properties.views.unit_img_view import UnitImagePrimaryView

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
        "<uuid:pk>/",
        PropertyDetailView.as_view(),
        name="property-detail",
    ),
    path(
        "<uuid:pk>/edit/",
        PropertyUpdateView.as_view(),
        name="property-edit",
    ),
    path(
        "<uuid:pk>/configure/",
        PropertyConfigurationView.as_view(),
        name="property-configure",
    ),
    path(
        "<uuid:pk>/images/",
        PropertyImagesView.as_view(),
        name="property-images",
    ),
    path(
        "<uuid:pk>/delete/",
        PropertyDeleteView.as_view(),
        name="property-delete",
    ),
]

urlpatterns += [
    path(
        "<uuid:property_id>/images/add/",
        PropertyImageCreateView.as_view(),
        name="property-image-add",
    ),
    path(
        "images/<uuid:image_id>/primary/",
        PropertyImagePrimaryView.as_view(),
        name="property-image-primary",
    ),
    path(
        "images/<uuid:image_id>/edit/",
        PropertyImageUpdateView.as_view(),
        name="property-image-edit",
    ),
    path(
        "images/<uuid:image_id>/delete/",
        PropertyImageDeleteView.as_view(),
        name="property-image-delete",
    ),
]

urlpatterns += [
    path(
        "buildings/<uuid:pk>/",
        BuildingDetailView.as_view(),
        name="building-detail",
    ),
    path(
        "buildings/<uuid:pk>/edit/",
        BuildingUpdateView.as_view(),
        name="building-edit",
    ),
    path(
        "<uuid:property_id>/buildings/create/",
        BuildingCreateView.as_view(),
        name="property-buildings-create",
    ),
    path(
        "<uuid:property_id>/buildings/<uuid:building_id>/units/",
        UnitListView.as_view(),
        name="unit-list",
    ),
    path(
        "<uuid:property_id>/buildings/<uuid:building_id>/units/create/",
        UnitCreateView.as_view(),
        name="unit-create",
    ),
    path(
        "units/<uuid:pk>/",
        UnitDetailView.as_view(),
        name="unit-detail",
    ),
    path(
        "units/<uuid:pk>/edit/",
        UnitUpdateView.as_view(),
        name="unit-edit",
    ),
    path(
        "units/<uuid:pk>/delete/",
        UnitDeleteView.as_view(),
        name="unit-delete",
    ),
    path(
        "units/<uuid:pk>/images/",
        UnitImagesView.as_view(),
        name="unit-images",
    ),
    path(
        "units/<uuid:unit_id>/images/add/",
        UnitImageCreateView.as_view(),
        name="unit-image-add",
    ),
    path(
        "unit-images/<uuid:image_id>/primary/",
        UnitImagePrimaryView.as_view(),
        name="unit-image-primary",
    ),
    path(
        "unit-images/<uuid:image_id>/delete/",
        UnitImageDeleteView.as_view(),
        name="unit-image-delete",
    ),
]
