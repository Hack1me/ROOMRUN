from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View

from properties.forms import PropertyImageForm
from properties.mixins import ServiceFormMixin
from properties.mixins import UnitImageAccessMixin
from properties.services import PropertyImageService


class UnitImageCreateView(UnitImageAccessMixin, ServiceFormMixin, View):
    """Upload one image for a unit owned by the current landlord."""

    def post(self, request, unit_id):
        unit = self.get_unit(unit_id)
        form = PropertyImageForm(request.POST, request.FILES)

        if not form.is_valid():
            self.add_form_errors_as_messages(form)
            return redirect("properties:unit-images", pk=unit.pk)

        try:
            PropertyImageService.create(unit=unit, data=form.cleaned_data)
        except ValidationError as exc:
            self.handle_service_errors(form, exc)
            self.add_form_errors_as_messages(form)
            return redirect("properties:unit-images", pk=unit.pk)

        return self.service_success(
            _("Image added successfully."),
            "properties:unit-images",
            pk=unit.pk,
        )


class UnitImagePrimaryView(UnitImageAccessMixin, ServiceFormMixin, View):
    """Mark a unit image as the primary image."""

    def post(self, request, image_id):
        image = self.get_image(image_id)
        try:
            PropertyImageService.set_primary(image=image)
        except Exception:  # noqa: BLE001
            messages.error(request, _("Unable to update the primary image."))
        else:
            messages.success(request, _("Primary image updated successfully."))
        return redirect("properties:unit-images", pk=image.unit_id)


class UnitImageDeleteView(UnitImageAccessMixin, ServiceFormMixin, View):
    """Delete an image belonging to a unit."""

    def post(self, request, image_id):
        image = self.get_image(image_id)
        unit_id = image.unit_id
        try:
            PropertyImageService.delete(image=image)
        except Exception:  # noqa: BLE001
            messages.error(request, _("Unable to delete the image."))
        else:
            messages.success(request, _("Image deleted successfully."))
        return redirect("properties:unit-images", pk=unit_id)
