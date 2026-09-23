from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from maintenance.models import MaintenanceRequest
from properties.models import Unit
from users.models import MaintenanceAgent
from utils.enums import EmployeeStatus
from utils.enums import Priority


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """Validate each uploaded photo before it reaches persistent storage."""

    widget = MultipleImageInput
    max_photos = 5

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data]
        files = [file for file in files if file]
        if len(files) > self.max_photos:
            raise ValidationError(_("You can attach at most 5 photos."))

        cleaned_files = []
        for uploaded_file in files:
            if uploaded_file.size > 5 * 1024 * 1024:
                raise ValidationError(_("Each photo must be 5 MB or smaller."))
            cleaned_file = super().clean(uploaded_file, initial)
            if getattr(cleaned_file.image, "format", "").upper() not in {
                "JPEG",
                "PNG",
                "WEBP",
            }:
                raise ValidationError(_("Photos must be JPG, PNG or WebP files."))
            cleaned_files.append(cleaned_file)
        return cleaned_files


class MaintenanceRequestForm(forms.ModelForm):
    photos = MultipleImageField(
        required=False,
        label=_("Photos"),
        help_text=_("Optional: up to 5 JPG, PNG or WebP photos (5 MB each)."),
        widget=MultipleImageInput(
            attrs={"accept": "image/jpeg,image/png,image/webp", "multiple": True}
        ),
    )

    class Meta:
        model = MaintenanceRequest
        fields = ("title", "description", "priority")
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "maxlength": 150}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 6}),
            "priority": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_priority(self):
        priority = self.cleaned_data["priority"]
        if priority == Priority.URGENT:
            # The UI does not turn an urgent issue into an emergency service.
            # This explicit copy is intentionally retained as a safety reminder.
            return priority
        return priority


class LandlordMaintenanceRequestForm(MaintenanceRequestForm):
    unit = forms.ModelChoiceField(queryset=Unit.objects.none(), label=_("Unit"))
    maintenance_agent = forms.ModelChoiceField(
        queryset=MaintenanceAgent.objects.none(), label=_("Maintenance agent")
    )

    class Meta(MaintenanceRequestForm.Meta):
        fields = ("unit", "title", "description", "priority")

    def __init__(self, *args, landlord, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unit"].queryset = (
            Unit.objects.filter(
                building__property_ref__landlord=landlord,
                rental_contracts__status="ACTIVE",
            )
            .distinct()
            .select_related("building", "building__property_ref")
        )
        self.fields["maintenance_agent"].queryset = MaintenanceAgent.objects.filter(
            landlords=landlord, employee__status=EmployeeStatus.ACTIVE
        ).select_related("employee__user")
        self.fields["unit"].widget.attrs["class"] = "form-select"
        self.fields["maintenance_agent"].widget.attrs["class"] = "form-select"


class TaskProgressForm(forms.Form):
    action = forms.ChoiceField(
        choices=(("start", _("Start work")), ("complete", _("Mark as completed"))),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    work_notes = forms.CharField(
        required=False,
        max_length=4000,
        widget=forms.Textarea(
            attrs={
                "class": "form-textarea",
                "rows": 5,
                "placeholder": _(
                    "Describe the work performed, parts used or next steps."
                ),
            }
        ),
        label=_("Work notes"),
    )

    def __init__(self, *args, task=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.task = task
        if task and task.status == "IN_PROGRESS":
            self.fields["action"].choices = (("complete", _("Mark as completed")),)
        elif task and task.status not in {"ASSIGNED", "PENDING"}:
            self.fields["action"].choices = ()
