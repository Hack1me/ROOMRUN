# properties/services/property.py

from typing import TYPE_CHECKING

from django.db import transaction
from properties.models import Building
from properties.models import Property
from properties.models import PropertyImage
from properties.models import Unit

if TYPE_CHECKING:
    from users.models import Landlord


class BaseService:
    """
    Base class for property services.

    Provides shared helpers for:
    - Applying a whitelist of fields from ``data`` onto an existing model
      instance without overwriting unchanged fields.
    - Saving only the fields that actually changed, including ``updated_at``
      when the model tracks it.
    """

    ALLOWED_UPDATE_FIELDS: set[str] = set()

    @classmethod
    def _apply_changes(cls, obj, data: dict):
        """
        Apply only whitelisted fields from ``data`` onto ``obj`` and save.

        Fields not listed in ``ALLOWED_UPDATE_FIELDS`` or not present on
        ``obj`` are ignored. Only fields whose value actually changed are
        included in the ``update_fields`` save.

        Args:
            obj: The model instance to update in place.
            data: A dict of candidate field values.

        Returns:
            The updated model instance.
        """
        changed_fields = []
        allowed = cls.ALLOWED_UPDATE_FIELDS

        for field, value in data.items():
            if field not in allowed:
                continue
            if not hasattr(obj, field):
                continue
            if getattr(obj, field) != value:
                setattr(obj, field, value)
                changed_fields.append(field)

        if changed_fields:
            obj.full_clean()
            if hasattr(obj, "updated_at"):
                changed_fields.append("updated_at")
            obj.save(update_fields=changed_fields)

        return obj


class PropertyService:
    """
    Service responsible for managing property instances.
    All operations are atomic and enforce business rules.
    """

    # Fields that can be updated via the service
    ALLOWED_UPDATE_FIELDS = {
        "name",
        "property_type",
        "description",
        "address",
        "country",
        "region",
        "city",
        "status",
        "default_currency",
        "default_monthly_rent",
        "tenant_management_enabled",
        "maintenance_management_enabled",
    }

    @staticmethod
    @transaction.atomic
    def create(*, landlord: Landlord, data: dict) -> Property:
        """
        Create a new property owned by the given landlord.

        Args:
            landlord: The landlord who owns the property.
            data: A dict with the property fields.

        Returns:
            The created Property instance.
        """
        # Prevent landlord from being passed twice
        data.pop("landlord", None)

        property_obj = Property(landlord=landlord, **data)
        property_obj.full_clean()
        property_obj.save()

        return property_obj

    @staticmethod
    @transaction.atomic
    def update(*, property_obj: Property, data: dict) -> Property:
        """
        Update a property with the given data.

        Only fields in ALLOWED_UPDATE_FIELDS are considered.

        Args:
            property_obj: The property instance to update.
            data: A dict with the fields to update.

        Returns:
            The updated Property instance.
        """
        BaseService._apply_changes(property_obj, data)
        return property_obj

    @staticmethod
    @transaction.atomic
    def delete(*, property_obj: Property) -> None:
        """
        Delete the given property.

        Args:
            property_obj: The property instance to delete.
        """
        property_obj.delete()

# Property Image Service
class PropertyImageService:
    """
    Service for managing PropertyImage instances.
    Ensures only one image per property is marked as primary.
    """

    # Fields that can be updated via the service
    ALLOWED_UPDATE_FIELDS = {
        "image",
        "caption",
        "is_primary",
    }

    @staticmethod
    @transaction.atomic
    def create(*, property_obj: Property, data: dict) -> PropertyImage:
        """
        Create a new image for a property.

        If `is_primary` is True, all other images for the property
        are unset as primary.
        """
        # Prevent property from being passed twice
        data.pop("property", None)

        # Unset other primary images if this one is primary
        if data.get("is_primary"):
            PropertyImage.objects.filter(
                property=property_obj,
                is_primary=True,
            ).update(is_primary=False)

        image = PropertyImage(property=property_obj, **data)
        image.full_clean()
        image.save()

        return image

    @staticmethod
    @transaction.atomic
    def update(*, image: PropertyImage, data: dict) -> PropertyImage:
        """
        Update an existing image.

        Only fields in ALLOWED_UPDATE_FIELDS are considered.
        If `is_primary` becomes True, other primary images are unset.
        """
        allowed = PropertyImageService.ALLOWED_UPDATE_FIELDS

        # Unset other primary images if this one becomes primary
        if data.get("is_primary"):
            PropertyImage.objects.filter(
                property=image.property,
                is_primary=True,
            ).exclude(pk=image.pk).update(is_primary=False)

        BaseService._apply_changes(image, data)
        return image

    @staticmethod
    @transaction.atomic
    def set_primary(*, image: PropertyImage) -> PropertyImage:
        """
        Mark the given image as primary and unset all others for the same property.
        """
        PropertyImage.objects.filter(
            property=image.property,
            is_primary=True,
        ).exclude(pk=image.pk).update(is_primary=False)

        image.is_primary = True

        update_fields = ["is_primary"]
        if hasattr(image, "updated_at"):
            update_fields.append("updated_at")

        image.save(update_fields=update_fields)

        return image

    @staticmethod
    @transaction.atomic
    def delete(*, image: PropertyImage) -> None:
        """
        Delete the given image.

        If the deleted image was primary, another image (if any) could
        be promoted automatically — consider adding this behavior if needed.
        """

        was_primary = image.is_primary
        property_obj = image.property

        image.delete()

        if was_primary:
            next_image = property_obj.images.first()
        if next_image:
            next_image.is_primary = True
            next_image.save(update_fields=["is_primary"])

# Building Service
class BuildingService:
    """
    Service responsible for managing Building instances.
    All operations are atomic and enforce business rules.
    """

    # Fields that can be updated via the service
    ALLOWED_UPDATE_FIELDS = {
        "name",
        "description",
        "floors",
        "status",
    }

    @staticmethod
    @transaction.atomic
    def create(*, property_obj: Property, data: dict) -> Building:
        """
        Create a new building within the given property.

        Args:
            property_obj: The property the building belongs to.
            data: A dict with the building fields.

        Returns:
            The created Building instance.
        """
        # Prevent property from being passed twice
        data.pop("property", None)

        building = Building(property_ref=property_obj, **data)
        building.full_clean()
        building.save()

        return building

    @staticmethod
    @transaction.atomic
    def update(*, building: Building, data: dict) -> Building:
        """
        Update a building with the given data.

        Only fields in ALLOWED_UPDATE_FIELDS are considered.

        Args:
            building: The building instance to update.
            data: A dict with the fields to update.

        Returns:
            The updated Building instance.
        """
        BaseService._apply_changes(building, data)
        return building

    @staticmethod
    @transaction.atomic
    def delete(*, building: Building) -> None:
        """
        Delete the given building.

        Args:
            building: The building instance to delete.
        """
        building.delete()


class UnitService:
    """
    Service responsible for managing Unit instances.
    All operations are atomic and enforce business rules.
    """

    # Fields that can be updated via the service
    ALLOWED_UPDATE_FIELDS = {
        "unit_number",
        "floor",
        "unit_type",
        "bedrooms",
        "bathrooms",
        "area",
        "monthly_rent",
        "status",
    }

    @staticmethod
    @transaction.atomic
    def create(*, building: Building, data: dict) -> Unit:
        """
        Create a new unit within the given building.

        Args:
            building: The building the unit belongs to.
            data: A dict with the unit fields.

        Returns:
            The created Unit instance.
        """
        # Prevent building from being passed twice
        data.pop("building", None)

        unit = Unit(building=building, **data)
        unit.full_clean()
        unit.save()

        return unit

    @staticmethod
    @transaction.atomic
    def update(*, unit: Unit, data: dict) -> Unit:
        """
        Update a unit with the given data.

        Only fields in ALLOWED_UPDATE_FIELDS are considered.

        Args:
            unit: The unit instance to update.
            data: A dict with the fields to update.

        Returns:
            The updated Unit instance.
        """
        BaseService._apply_changes(unit, data)
        return unit

    @staticmethod
    @transaction.atomic
    def delete(*, unit: Unit) -> None:
        """
        Delete the given unit.

        Args:
            unit: The unit instance to delete.
        """
        unit.delete()
