# properties/views/property_image.py

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from properties.forms import PropertyImageForm
from properties.mixins import PropertyImageAccessMixin
from properties.mixins import ServiceFormMixin
from properties.services import PropertyImageService


class PropertyImageCreateView(PropertyImageAccessMixin, ServiceFormMixin, View):
    """
    Create a new image for a property owned by the authenticated landlord.

    Handles POST only. Uploads are validated by the form and the model.
    """

    def post(self, request, property_id):
        property_obj = self.get_property(property_id)

        form = PropertyImageForm(
            request.POST,
            request.FILES,
        )

        if not form.is_valid():
            self.add_form_errors_as_messages(form)
            return redirect(
                "properties:property-detail",
                pk=property_obj.pk,
            )

        try:
            PropertyImageService.create(
                property_obj=property_obj,
                data=form.cleaned_data,
            )
        except ValidationError as e:
            self.handle_service_errors(form, e)
            self.add_form_errors_as_messages(form)
            return redirect(
                "properties:property-detail",
                pk=property_obj.pk,
            )

        return self.service_success(
            _("Image added successfully."),
            "properties:property-detail",
            pk=property_obj.pk,
        )


class PropertyImagePrimaryView(PropertyImageAccessMixin, ServiceFormMixin, View):
    """
    Mark a property image as the primary image.

    Only accessible to the landlord who owns the property.
    """

    def post(self, request, image_id):
        image = self.get_image(image_id)

        try:
            PropertyImageService.set_primary(image=image)
        except Exception:  # noqa: BLE001
            messages.error(
                request,
                _("Unable to update the primary image."),
            )
            return redirect(
                "properties:property-detail",
                pk=image.property.pk,
            )

        return self.service_success(
            _("Primary image updated successfully."),
            "properties:property-detail",
            pk=image.property.pk,
        )


class PropertyImageDeleteView(PropertyImageAccessMixin, ServiceFormMixin, View):
    """
    Delete a property image.

    Only accessible to the landlord who owns the property.
    Uses POST only (state-changing action).
    """

    def post(self, request, image_id):
        """
        Handle the request to delete the given image.

        Args:
            image_id: The UUID or integer PK of the PropertyImage.

        Redirects back to the property detail page on success or failure.
        """
        image = self.get_image(image_id)
        property_obj = image.property  # avoid shadowing builtin `property`

        try:
            PropertyImageService.delete(image=image)
        except Exception:  # noqa: BLE001
            messages.error(
                request,
                _("Unable to delete the image."),
            )
            return redirect(
                "properties:property-detail",
                pk=property_obj.pk,
            )

        return self.service_success(
            _("Image deleted successfully."),
            "properties:property-detail",
            pk=property_obj.pk,
        )


class PropertyImageUpdateView(PropertyImageAccessMixin, ServiceFormMixin, View):
    """
    Update an existing property image.

    Only accessible to the landlord who owns the property.
    Uses POST only.
    """

    def post(self, request, image_id):
        """
        Handle the request to update the given image.

        Args:
            image_id: The UUID or integer PK of the PropertyImage.
        """
        image = self.get_image(image_id)
        property_obj = image.property
        redirect_url = "properties:property-detail"

        form = PropertyImageForm(
            request.POST,
            request.FILES,
            instance=image,
        )

        if not form.is_valid():
            self.add_form_errors_as_messages(form)
            return redirect(redirect_url, pk=property_obj.pk)

        try:
            PropertyImageService.update(
                image=image,
                data=form.cleaned_data,
            )
        except ValidationError as e:
            self.handle_service_errors(form, e)
            self.add_form_errors_as_messages(form)
            return redirect(redirect_url, pk=property_obj.pk)

        return self.service_success(
            _("Image updated successfully."),
            redirect_url,
            pk=property_obj.pk,
        )
