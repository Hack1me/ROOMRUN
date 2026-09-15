from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from properties.models import Unit
from rentals.models import RentalApplication
from utils.enums import UnitStatus


class RentalApplicationForm(forms.ModelForm):
    """
    Form used by tenants to submit a rental application for a unit.
    """

    class Meta:
        model = RentalApplication
        fields = (
            "unit",
            "desired_move_in_date",
            "desired_duration",
            "occupants_count",
            "message",
        )

        widgets = {
            "unit": forms.Select(attrs={"class": "form-select"}),
            "desired_move_in_date": forms.DateInput(
                attrs={"type": "date", "class": "form-input"}
            ),
            "desired_duration": forms.NumberInput(
                attrs={"min": 1, "class": "form-input"}
            ),
            "occupants_count": forms.NumberInput(
                attrs={"min": 1, "class": "form-input"}
            ),
            "message": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "form-textarea",
                    "placeholder": _("Tell the landlord about your application..."),
                }
            ),
        }

        labels = {
            "unit": _("Unit"),
            "desired_move_in_date": _("Desired move-in date"),
            "desired_duration": _("Desired rental duration (months)"),
            "occupants_count": _("Number of occupants"),
            "message": _("Message"),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        """
        Initialize the form with an optional tenant to filter units and
        enforce duplicate prevention.
        """
        super().__init__(*args, **kwargs)
        self.tenant = tenant

        self.fields["unit"].queryset = (
            Unit.objects
            .select_related("building", "building__property_ref__landlord")
            .filter(status=UnitStatus.AVAILABLE)
        )

        # These fields are required for a new application.
        self.fields["desired_move_in_date"].required = True
        self.fields["desired_duration"].required = True
        self.fields["occupants_count"].required = True

    # -------------------------------------------------------------------------
    # Field-level validation
    # -------------------------------------------------------------------------

    def clean_desired_move_in_date(self):
        """Ensure the desired move-in date is in the future."""
        move_in_date = self.cleaned_data["desired_move_in_date"]
        if move_in_date and move_in_date < timezone.now().date():
            raise forms.ValidationError(
                _("The desired move-in date must be in the future.")
            )
        return move_in_date

    def clean_desired_duration(self):
        """Ensure the duration is at least 1 month."""
        duration = self.cleaned_data["desired_duration"]
        if duration is not None and duration < 1:
            raise forms.ValidationError(
                _("Rental duration must be at least 1 month.")
            )
        return duration

    def clean_occupants_count(self):
        """Ensure there is at least one occupant."""
        occupants = self.cleaned_data["occupants_count"]
        if occupants is not None and occupants < 1:
            raise forms.ValidationError(
                _("There must be at least one occupant.")
            )
        return occupants

    # -------------------------------------------------------------------------
    # Cross-field validation
    # -------------------------------------------------------------------------

    def clean(self):
        """
        Prevent duplicate applications from the same tenant
        for the same unit while one is still pending.
        """
        cleaned_data = super().clean()
        unit = cleaned_data.get("unit")

        if self.tenant and unit:
            exists = RentalApplication.objects.filter(
                tenant=self.tenant,
                unit=unit,
                status="PENDING",
            ).exists()
            if exists:
                raise forms.ValidationError(
                    _("You already have a pending application for this unit.")
                )

        return cleaned_data
