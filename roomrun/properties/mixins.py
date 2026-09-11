from typing import TYPE_CHECKING

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from properties.models import Building
from properties.models import Property
from properties.models import PropertyImage
from properties.models import Unit

if TYPE_CHECKING:
    from users.models import Landlord


class LandlordRequiredMixin(LoginRequiredMixin):
    """
    Ensure the authenticated user is a landlord.

    Enforces landlord access in dispatch(). If the user is authenticated
    but not a landlord, they are redirected (or a PermissionDenied is raised
    depending on the ``LANDLORD_DENIED_BEHAVIOR`` attribute).
    """

    # Set to "redirect" to redirect with a message, or "raise" for a 403.
    LANDLORD_DENIED_BEHAVIOR = "redirect"
    LANDLORD_DENIED_REDIRECT_URL = "dashboard:entry"

    def get_landlord(self) -> Landlord:
        """Return the landlord profile or raise PermissionDenied."""
        try:
            return self.request.user.landlord_profile
        except AttributeError as exc:
            raise PermissionDenied from exc

    def dispatch(self, request, *args, **kwargs):
        """
        Enforce landlord access before the view runs.
        """
        # Ensure the user is authenticated first (LoginRequiredMixin)
        response = super().dispatch(request, *args, **kwargs)
        if response:
            return response

        if not hasattr(request.user, "landlord_profile"):
            if self.LANDLORD_DENIED_BEHAVIOR == "redirect":
                messages.error(
                    request,
                    _("You do not have access to the landlord area."),
                )
                return redirect(self.LANDLORD_DENIED_REDIRECT_URL)

            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

class LandlordPropertyMixin(LandlordRequiredMixin):
    """
    Provides a helper to fetch a property owned by the current landlord.
    Prevents duplicating this logic across views.
    """

    def get_property(self, pk: int) -> Property:
        return get_object_or_404(
            Property,
            pk=pk,
            landlord=self.get_landlord(),
        )

# Property Image Mixin
class PropertyImageAccessMixin(LoginRequiredMixin):
    """
    Provides access control helpers for PropertyImage views.

    Ensures that:
    - The user is authenticated (via LoginRequiredMixin).
    - The user has a landlord profile.
    - Properties and images are scoped to the authenticated landlord.
    """

    # Optional: redirect behavior when landlord profile is missing
    LANDLORD_DENIED_REDIRECT_URL = "dashboard:entry"

    def get_landlord(self) -> Landlord:
        """
        Return the authenticated user's landlord profile.

        Raises:
            PermissionDenied: If the user does not have a landlord profile.
        """
        try:
            return self.request.user.landlord_profile
        except AttributeError as exc:
            raise PermissionDenied from exc

    def get_property(self, property_id) -> Property:
        """
        Fetch a property owned by the authenticated landlord.

        Args:
            property_id: The UUID or integer PK of the property.

        Returns:
            The Property instance.

        Raises:
            Http404: If the property does not exist or is not owned by the landlord.
        """
        return get_object_or_404(
            Property,
            pk=property_id,
            landlord=self.get_landlord(),
        )

    def get_image(self, image_id) -> PropertyImage:
        """
        Fetch a property image whose parent property is owned by the
        authenticated landlord.

        Args:
            image_id: The UUID or integer PK of the image.

        Returns:
            The PropertyImage instance.

        Raises:
            Http404: If the image does not exist or its property is not
            owned by the landlord.
        """
        return get_object_or_404(
            PropertyImage,
            pk=image_id,
            property__landlord=self.get_landlord(),
        )

class LandlordBuildingAccessMixin(LandlordRequiredMixin):
    """
    Provides helpers to fetch properties and buildings scoped to the
    authenticated landlord.
    """

    def get_property(self, property_id) -> Property:
        return get_object_or_404(
            Property,
            pk=property_id,
            landlord=self.get_landlord(),
        )

    def get_building(self, pk) -> Building:
        return get_object_or_404(
            Building.objects.select_related("property_ref"),
            pk=pk,
            property_ref__landlord=self.get_landlord(),
        )


class ServiceFormMixin:
    """
    Mixin to factorize common form + service interaction patterns.

    Provides helpers for:
    - Mapping service ValidationError back onto form fields.
    - Rendering the form template with the proper base context.
    - Sending a success message and redirecting.
    - Surfacing form errors as global messages (for POST-only views that
      redirect instead of re-rendering).
    """

    def handle_service_errors(self, form, exception: ValidationError):
        """Add each error from a service ValidationError back onto the form."""
        for field, errors in exception.message_dict.items():
            for error in errors:
                form.add_error(field, error)

    def add_form_errors_as_messages(self, form):
        """Surface each form error as a global message (for redirect flows)."""
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")

    def render_form(self, form, context: dict):
        """Render the view's template with the given form and context."""
        base_context = {"form": form}
        base_context.update(context)
        return render(request=self.request, template_name=self.template_name, context=base_context)

    def service_success(self, message, url_name, **kwargs):
        """Flash a success message and redirect to the given named URL."""
        messages.success(self.request, message)
        return redirect(url_name, **kwargs)


class LandlordUnitAccessMixin(LandlordRequiredMixin):
    """
    Provides helpers to fetch buildings and units scoped to the
    authenticated landlord.
    """

    def get_building(self, property_id, building_id) -> Building:
        """
        Fetch a building that belongs to a property owned by the landlord.
        """
        return get_object_or_404(
            Building.objects.select_related("property_ref"),
            id=building_id,
            property_ref_id=property_id,
            property_ref__landlord=self.get_landlord(),
        )

    def get_unit(self, pk) -> Unit:
        """
        Fetch a unit whose parent building's property is owned by the landlord.
        """
        return get_object_or_404(
            Unit.objects.select_related("building", "building__property_ref"),
            id=pk,
            building__property_ref__landlord=self.get_landlord(),
        )
