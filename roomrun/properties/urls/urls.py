from django.urls import path
from properties.views.property_img_view import PropertyImageCreateView
from properties.views.property_img_view import PropertyImageDeleteView
from properties.views.property_img_view import PropertyImagePrimaryView
from properties.views.property_img_view import PropertyImageUpdateView
from properties.views.property_view import PropertyCreateView
from properties.views.property_view import PropertyDeleteView
from properties.views.property_view import PropertyDetailView
from properties.views.property_view import PropertyListView
from properties.views.property_view import PropertyUpdateView
from properties.views.unit_view import UnitCreateView
from properties.views.unit_view import UnitDeleteView
from properties.views.unit_view import UnitDetailView
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
]
