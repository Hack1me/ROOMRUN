from cities_light.models import City
from cities_light.models import Region
from core.models import BaseModel
from core.validators import validate_image_extension
from core.validators import validate_image_size
from django.db import models
from django.db.models import Q
from django.urls import reverse as safe_reverse
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from smart_selects.db_fields import ChainedForeignKey
from users.models import Landlord
from utils.enums import PropertyStatus
from utils.enums import PropertyType
from utils.enums import UnitStatus
from utils.enums import UnitType
from utils.helpers import property_image_upload_path


# PROPERTY
class Property(BaseModel):
    """
    Represents a property managed by a landlord in ROOMRUN.
    A property can contain one or more buildings.
    Inherits from BaseModel, which provides `id`, `created_at`, and `updated_at`.
    """

    reference_field = "property_number"
    reference_prefix = "PRP"

    # -------------------------------------------------------------------------
    # Inner Choices Class
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    landlord = models.ForeignKey(
        Landlord,
        on_delete=models.PROTECT,
        related_name="properties",  # Allows accessing `landlord.properties.all()`.  # noqa: E501
        verbose_name=_("Landlord"),
        null=False,
        help_text=_("The landlord who owns this property."),
    )

    property_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,  # Not editable via forms; automatically generated.  # noqa: E501
        blank=True,
        verbose_name=_("Property number"),
        help_text=_("Auto-generated unique identifier for the property."),
        # Generation logic is provided via a `pre_save` signal.
    )

    name = models.CharField(
        max_length=150,
        verbose_name=_("Property name"),
        help_text=_("The official name of the property (e.g., 'Sunset Tower')."),
    )

    property_type = models.CharField(
        max_length=30,
        choices=PropertyType.choices,
        default=PropertyType.RESIDENTIAL,
        verbose_name=_("Property type"),
        help_text=_("The type of the property (e.g., Residential, Commercial)."),
    )

    description = models.TextField(
        blank=True,  # Optional field; can be left empty.
        verbose_name=_("Description"),
        help_text=_(
            "Additional details about the property, such as amenities or history."
        ),
    )

    address = models.CharField(
        max_length=255,
        verbose_name=_("Address"),
        help_text=_("Street address of the property (e.g., '123 Main St')."),
    )

    city = ChainedForeignKey(
        City,
        chained_field="region",
        chained_model_field="region",
        show_all=False,
        auto_choose=True,
        sort=True,
        null=True,
        blank=True,
        verbose_name=_("City"),
        help_text=_("City where the property is located."),
    )

    country = models.ForeignKey(
        "cities_light.Country",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("Country where the property is located."),
        verbose_name=_("Country"),
    )
    region = ChainedForeignKey(
        Region,
        chained_field="country",
        chained_model_field="country",
        show_all=False,
        auto_choose=True,
        sort=True,
        null=True,
        blank=True,
        help_text=_("Region where the property is located."),
        verbose_name=_("Region"),
    )
    status = models.CharField(
        max_length=30,
        choices=PropertyStatus.choices,
        default=PropertyStatus.ACTIVE,
        verbose_name=_("Status"),
        help_text=_("Current operational status of the property."),
    )

    default_currency = models.CharField(
        max_length=3,
        choices=[
            ("XAF", "XAF — CFA Franc"),
            ("EUR", "EUR — Euro"),
            ("USD", "USD — US Dollar"),
        ],
        default="XAF",
        verbose_name=_("Default currency"),
        help_text=_("Default currency used for rent and charges in this property."),
    )

    default_monthly_rent = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Default monthly rent"),
        help_text=_("Suggested monthly rent amount for new units in this property."),
    )

    tenant_management_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Tenant management"),
        help_text=_("Allow ROOMRUN to manage tenants and rental contracts for this property."),
    )

    maintenance_management_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Maintenance management"),
        help_text=_("Allow maintenance requests to be associated with this property."),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "properties"  # Explicit table name in the database.
        ordering = ["-created_at"]  # Default ordering: newest first.
        verbose_name = _("Property")
        verbose_name_plural = _("Properties")

        indexes = [
            models.Index(fields=["landlord"], name="property_landlord_idx"),
            # Speeds up queries filtering by landlord.
            models.Index(fields=["status"], name="property_status_idx"),
            # Speeds up queries filtering by status.
            models.Index(fields=["city"], name="property_city_idx"),
            # Speeds up queries filtering by city (e.g., for location-based searches).
        ]

    # -------------------------------------------------------------------------
    # Standard Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the property name as its string representation."""
        return self.name

    def get_absolute_url(self) -> str:
        """Return the canonical URL for the property detail page."""
        return safe_reverse("properties:property-detail", kwargs={"pk": self.id})

    # -------------------------------------------------------------------------
    # Computed Properties (Derived from Related Models)
    # -------------------------------------------------------------------------

    @property
    def total_buildings(self) -> int:
        """
        Return the total number of buildings associated with this property.
        """
        return self.buildings.count()

    @property
    def total_units(self) -> int:
        """
        Return the total number of rental units across all buildings.
        """
        from django.db.models import Count  # noqa: PLC0415

        result = self.buildings.aggregate(total=Count("units"))["total"]
        return result or 0  # Return 0 if no buildings exist or no units are defined.


# PROPERTYIMAGES
class PropertyImage(BaseModel):
    """
    Represents an image associated with either a property or a unit.

    Exactly one owner (property or unit) must be set — enforced by
    database constraints. The 'is_primary' flag marks the main image
    for that owner.
    """

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="images",
        null=True,
        blank=True,
        verbose_name=_("Property"),
        help_text=_("The property this image belongs to."),
    )
    unit = models.ForeignKey(
        "Unit",
        on_delete=models.CASCADE,
        related_name="images",
        null=True,
        blank=True,
        verbose_name=_("Unit"),
        help_text=_("The unit this image belongs to."),
    )

    image = models.ImageField(
        _("Image"),
        upload_to=property_image_upload_path,
        help_text=_(
            "Upload a JPG, PNG, or WebP image. "
            "Recommended size: 1920*1080 pixels, max 5MB."
        ),
        validators=[
            validate_image_size,
            validate_image_extension,
            # validate_image_dimensions,   # optional
        ],
        # Optional: add validators for size/dimensions here
    )

    caption = models.CharField(
        max_length=255,
        default="Property Image",
        verbose_name=_("Caption"),
        help_text=_("A short description of the image."),
    )

    is_primary = models.BooleanField(
        default=False,
        verbose_name=_("Primary image"),
        help_text=_(
            "Mark this image as the main/cover image for the property. "
            "Only one image per property should be primary."
        ),
    )

    class Meta:
        db_table = "property_images"
        ordering = ["-is_primary", "-created_at"]
        verbose_name = _("Property image")
        verbose_name_plural = _("Property images")

        constraints = [
            # Exactly one of property or unit must be set (XOR).
            models.CheckConstraint(
                condition=(
                    Q(property__isnull=False, unit__isnull=True)
                    | Q(property__isnull=True, unit__isnull=False)
                ),
                name="image_exactly_one_owner",
            ),
        ]

        indexes = [
            models.Index(fields=["property"], name="property_image_property_idx"),
            models.Index(fields=["unit"], name="property_image_unit_idx"),
            models.Index(
                fields=["property", "is_primary"],
                name="property_image_primary_idx",
            ),
            models.Index(
                fields=["unit", "is_primary"],
                name="unit_image_primary_idx",
            ),
        ]

    def __str__(self) -> str:
        """Return a readable representation of the image."""
        if self.property_id:
            owner = f"Property: {self.property}"
        elif self.unit_id:
            owner = f"Unit: {self.unit}"
        else:
            owner = "Unknown owner"
        return f"{owner} - {self.caption}"
    def get_absolute_url(self) -> str:
        """
        Return the canonical URL for the image detail view.
        Note: In practice, images are often displayed as part of the property detail.
        """
        return safe_reverse("properties:property-image-detail", kwargs={"pk": self.id})

# BUILDING
class Building(BaseModel):
    """
    Represents a building belonging to a property in ROOMRUN.
    A building can contain one or more rental units.
    Inherits from BaseModel, which provides `id`, `created_at`, and `updated_at`.
    """

    reference_field = "building_number"
    reference_prefix = "BLD"

    # -------------------------------------------------------------------------
    # Inner Choices Class
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    property_ref = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="buildings",
        verbose_name=_("property"),
        help_text=_("The property that this building belongs to."),
    )

    building_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Building number"),
        help_text=_("Auto-generated unique identifier for the building."),
    )

    name = models.CharField(
        max_length=150,
        verbose_name=_("Building name"),
        help_text=_("The official name of the building (e.g., 'Tower A')."),
    )

    description = models.TextField(
        blank=True,  # Optional field; can be left empty.
        verbose_name=_("Description"),
        help_text=_(
            "Additional details about the building, such as amenities "
            "or construction year."
        ),
    )

    floors = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Number of floors"),
        help_text=_("Total number of floors in the building."),
    )

    status = models.CharField(
        max_length=30,
        choices=PropertyStatus.choices,
        default=PropertyStatus.ACTIVE,
        verbose_name=_("Status"),
        help_text=_("Current operational status of the building."),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "buildings"  # Explicit table name in the database.
        ordering = ["-created_at"]  # Default ordering: newest first.
        verbose_name = _("Building")
        verbose_name_plural = _("Buildings")

        indexes = [
            models.Index(fields=["property_ref"], name="building_property_idx"),
            # Speeds up queries filtering by property.
            models.Index(fields=["status"], name="building_status_idx"),
            # Speeds up queries filtering by status.
        ]

    # -------------------------------------------------------------------------
    # Standard Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the building name as its string representation."""
        return self.name

    def get_absolute_url(self) -> str:
        """Return the canonical URL for the building detail page."""
        return safe_reverse("properties:building-detail", kwargs={"pk": self.id})

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------

    @property
    def unit_count(self) -> int:
        """
        Return the total number of rental units in this building.
        This is a computed alternative to the stored `total_units` field.
        """
        return self.units.count()  # Requires a Unit model with related_name="units"


# UNIT
class Unit(BaseModel):
    """
    Represents an individual rental unit within a building in ROOMRUN.
    Each unit has a unique number within its building and specific attributes
    such as type, size, and rental price.
    Inherits from BaseModel, which provides `id`, `created_at`, and `updated_at`.
    """

    # -------------------------------------------------------------------------
    # Inner Choices Classes
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    building = models.ForeignKey(
        Building,
        on_delete=models.PROTECT,
        related_name="units",  # Allows accessing `building.units.all()`.
        verbose_name=_("Building"),
        help_text=_("The building that contains this unit."),
    )

    unit_number = models.CharField(
        max_length=50,
        verbose_name=_("Unit number"),
        help_text=_(
            "Unique unit identifier within the building. "
            "Must be unique per building (enforced by a database constraint)."
        ),
    )

    floor = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Floor"),
        help_text=_("Floor number where the unit is located (0 = ground floor)."),
    )

    unit_type = models.CharField(
        max_length=50,
        choices=UnitType.choices,
        default=UnitType.APARTMENT,
        verbose_name=_("Unit type"),
        help_text=_("Category of the unit (e.g., studio, apartment, office)."),
    )

    bedrooms = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Bedrooms"),
        help_text=_("Number of bedrooms in the unit."),
    )

    bathrooms = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Bathrooms"),
        help_text=_("Number of bathrooms in the unit."),
    )

    area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Area"),
        help_text=_("Total area of the unit in square meters."),
    )

    monthly_rent = MoneyField(
        max_digits=12,
        decimal_places=2,
        default_currency="XAF",
        verbose_name=_("Monthly rent"),
        help_text=_("Monthly rental price in the local currency."),
    )

    status = models.CharField(
        max_length=20,
        choices=UnitStatus.choices,
        default=UnitStatus.AVAILABLE,
        verbose_name=_("Status"),
        help_text=_("Current occupancy status of the unit."),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "units"  # Explicit table name in the database.
        ordering = [
            "building",
            "unit_number",
        ]  # Default ordering: by building, then unit number.
        verbose_name = _("Unit")
        verbose_name_plural = _("Units")

        constraints = [
            # Ensures that unit_number is unique per building.
            models.UniqueConstraint(
                fields=["building", "unit_number"],
                name="unique_unit_number_per_building",
            ),
        ]

        indexes = [
            models.Index(fields=["building"], name="unit_building_idx"),
            models.Index(fields=["status"], name="unit_status_idx"),
            models.Index(fields=["floor"], name="unit_floor_idx"),  # Added
            models.Index(fields=["unit_type"], name="unit_type_idx"),  # Added
        ]

    # -------------------------------------------------------------------------
    # Standard Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """
        Return a human-readable representation combining building name and unit number.
        """
        return f"{self.building.name} - {self.unit_number}"

    def get_absolute_url(self) -> str:
        """Return the canonical URL for the unit detail page."""
        return safe_reverse("properties:unit-detail", kwargs={"pk": self.id})
