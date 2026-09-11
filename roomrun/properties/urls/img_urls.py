# properties/urls.py

from django.urls import path
from properties.views import PropertyImageCreateView
from properties.views import PropertyImageDeleteView
from properties.views import PropertyImagePrimaryView
from properties.views import PropertyImageUpdateView

app_name = "properties"

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
