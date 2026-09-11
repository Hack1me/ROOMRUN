# properties/views/property_image.py

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from properties.forms import PropertyImageForm
from properties.mixins import PropertyImageAccessMixin
from properties.services import PropertyImageService


class PropertyImageCreateView(PropertyImageAccessMixin, View):
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

        # --- Form validation ---
        if not form.is_valid():
            # Surface each field error as a message for better UX
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

            return redirect(
                "properties:property-detail",
                pk=property_obj.pk,
            )

        # --- Service call with validation error handling ---
        try:
            PropertyImageService.create(
                property_obj=property_obj,
                data=form.cleaned_data,
            )
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return redirect(
                "properties:property-detail",
                pk=property_obj.pk,
            )

        messages.success(request, _("Image added successfully."))
        return redirect(
            "properties:property-detail",
            pk=property_obj.pk,
        )

# Set Primary Image
class PropertyImagePrimaryView(PropertyImageAccessMixin, View):
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

        messages.success(
            request,
            _("Primary image updated successfully."),
        )
        return redirect(
            "properties:property-detail",
            pk=image.property.pk,
        )

class PropertyImageDeleteView(PropertyImageAccessMixin, View):
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

        messages.success(
            request,
            _("Image deleted successfully."),
        )
        return redirect(
            "properties:property-detail",
            pk=property_obj.pk,
        )

class PropertyImageUpdateView(PropertyImageAccessMixin, View):
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

        # --- Form validation ---
        if not form.is_valid():
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return redirect(redirect_url, pk=property_obj.pk)

        # --- Service call with validation handling ---
        try:
            PropertyImageService.update(
                image=image,
                data=form.cleaned_data,
            )
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return redirect(redirect_url, pk=property_obj.pk)

        messages.success(request, _("Image updated successfully."))
        return redirect(redirect_url, pk=property_obj.pk)
