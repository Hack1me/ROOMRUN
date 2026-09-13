from django import forms
from django.utils.translation import gettext_lazy as _
from djmoney.forms.fields import MoneyField as MoneyFormField
from properties.models import Building
from properties.models import Property
from properties.models import PropertyImage
from properties.models import Unit


class PropertyForm(forms.ModelForm):
    """
    Form for creating and updating properties.
    Displays the country field with flag icons.
    """

    class Meta:
        model = Property
        fields = (
            "name",
            "property_type",
            "description",
            "address",
            "country",
            "region",
            "city",
            "status",
        )

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "autocomplete": "organization",
                }
            ),
            "property_type": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 4,
                }
            ),
            "address": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "autocomplete": "street-address",
                }
            ),
            "country": forms.Select(
                attrs={
                    "class": "form-select country-select",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name in ("country", "region", "city"):
            field = self.fields.get(field_name)
            if field is not None:
                field.required = True
                if hasattr(field.widget, "attrs"):
                    field.widget.attrs.setdefault("class", "")
                    field.widget.attrs["class"] += " form-select"
                    field.widget.attrs["class"] = field.widget.attrs["class"].strip()

    def clean_name(self):
        """Strip and validate the property name."""
        name = self.cleaned_data["name"].strip()

        if not name:
            raise forms.ValidationError(
                _("Property name cannot be empty.")
            )

        return name

    def clean_property_type(self):
        """Strip the property type field."""
        return self.cleaned_data["property_type"].strip()

    def clean_city(self):
        """Return the selected city."""
        return self.cleaned_data.get("city")

    def clean_region(self):
        """Return the selected region."""
        return self.cleaned_data.get("region")

    def clean_address(self):
        """Strip the address field."""
        return self.cleaned_data["address"].strip()

# Property Image Form
class PropertyImageForm(forms.ModelForm):
    """
    Form for uploading and editing property images.
    """

    class Meta:
        model = PropertyImage
        fields = (
            "image",
            "caption",
            "is_primary",
        )

        widgets = {
            "image": forms.ClearableFileInput(
                attrs={
                    "class": "form-input",
                    "accept": "image/jpeg,image/png,image/webp",
                }
            ),
            "caption": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": _("Image caption"),
                }
            ),
            "is_primary": forms.CheckboxInput(
                attrs={
                    "class": "form-checkbox",
                }
            ),
        }

        labels = {
            "image": _("Image"),
            "caption": _("Caption"),
            "is_primary": _("Set as primary image"),
        }

        help_texts = {
            "image": _("Upload a JPG, PNG, or WebP image. Max size: 5 MB."),
            "is_primary": _(
                "Mark this image as the main image for the property. "
                "Only one image per property should be primary."
            ),
        }

# Building Form
class BuildingForm(forms.ModelForm):
    """
    Form for creating and updating buildings.
    """

    class Meta:
        model = Building
        fields = (
            "name",
            "description",
            "floors",
            "status",
        )

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "autocomplete": "off",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 4,
                }
            ),
            "floors": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "min": 1,
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-input",
                }
            ),
        }

        labels = {
            "name": _("Building name"),
            "description": _("Description"),
            "floors": _("Number of floors"),
            "status": _("Status"),
        }

        help_texts = {
            "floors": _("The total number of floors in the building."),
        }

    def clean_name(self):
        """Strip and validate the building name."""
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError(_("Building name cannot be empty."))
        return name

    def clean_description(self):
        """Strip the description field."""
        return self.cleaned_data["description"].strip()

    def clean_floors(self):
        """Ensure the building has at least one floor."""
        floors = self.cleaned_data["floors"]
        if floors < 1:
            raise forms.ValidationError(
                _("A building must have at least one floor.")
            )
        return floors


class UnitForm(forms.ModelForm):
    """
    Form for creating and updating units.

    Handles validation for unit numbers, floor, rooms, and area.
    Supports django-money for the monthly rent.
    """

    # Explicitly declare the MoneyField to get the currency selector.
    monthly_rent = MoneyFormField(
        max_digits=12,
        decimal_places=2,
        required=True,
        label=_("Monthly rent"),
    )

    class Meta:
        model = Unit
        fields = (
            "unit_number",
            "floor",
            "unit_type",
            "bedrooms",
            "bathrooms",
            "area",
            "monthly_rent",
            "status",
        )
        widgets = {
            "unit_number": forms.TextInput(attrs={"class": "form-input"}),
            "floor": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "unit_type": forms.Select(attrs={"class": "form-input"}),
            "bedrooms": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "bathrooms": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "area": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "form-input"}),
        }

    # -------------------------------------------------------------------------
    # Validation methods
    # -------------------------------------------------------------------------

    def clean_unit_number(self):
        """Strip and validate the unit number."""
        unit_number = self.cleaned_data["unit_number"].strip()
        if not unit_number:
            raise forms.ValidationError(_("Unit number cannot be empty."))
        return unit_number

    def clean_floor(self):
        """Ensure the floor is not negative."""
        floor = self.cleaned_data["floor"]
        if floor < 0:
            raise forms.ValidationError(_("Floor cannot be negative."))
        return floor

    def clean_bedrooms(self):
        """Ensure the number of bedrooms is not negative."""
        bedrooms = self.cleaned_data["bedrooms"]
        if bedrooms < 0:
            raise forms.ValidationError(_("Bedrooms cannot be negative."))
        return bedrooms

    def clean_bathrooms(self):
        """Ensure there is at least one bathroom."""
        bathrooms = self.cleaned_data["bathrooms"]
        if bathrooms < 1:
            raise forms.ValidationError(_("A unit must have at least one bathroom."))
        return bathrooms

    def clean_area(self):
        """Ensure the area is positive if provided."""
        area = self.cleaned_data["area"]
        if area is not None and area <= 0:
            raise forms.ValidationError(_("Area must be greater than zero."))
        return area


class PropertyConfigurationForm(forms.ModelForm):
    """
    Form for configuring an existing property in Step 2 of the creation flow.
    """

    class Meta:
        model = Property
        fields = (
            "status",
            "default_currency",
            "default_monthly_rent",
            "tenant_management_enabled",
            "maintenance_management_enabled",
        )

        widgets = {
            "status": forms.RadioSelect(
                attrs={"class": "status-radio"},
            ),
            "default_currency": forms.Select(
                attrs={"class": "form-select"},
            ),
            "default_monthly_rent": forms.NumberInput(
                attrs={"class": "form-input", "min": 0, "step": "0.01"},
            ),
            "tenant_management_enabled": forms.CheckboxInput(
                attrs={"class": "form-checkbox"},
            ),
            "maintenance_management_enabled": forms.CheckboxInput(
                attrs={"class": "form-checkbox"},
            ),
        }

        labels = {
            "status": _("Property status"),
            "default_currency": _("Currency"),
            "default_monthly_rent": _("Default monthly rent"),
            "tenant_management_enabled": _("Enable tenant management"),
            "maintenance_management_enabled": _("Enable maintenance management"),
        }

    def clean_default_monthly_rent(self):
        """Ensure the default monthly rent is not negative."""
        rent = self.cleaned_data.get("default_monthly_rent")
        if rent is not None and rent < 0:
            raise forms.ValidationError(
                _("Default monthly rent cannot be negative.")
            )
        return rent
