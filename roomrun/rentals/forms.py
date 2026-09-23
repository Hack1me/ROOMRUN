import base64
import binascii

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.forms.fields import MoneyField as MoneyFormField
from properties.models import Unit
from rentals.models import RentalApplication
from rentals.models import RentalContract
from users.models import Tenant
from utils.enums import ApplicationStatus
from utils.enums import ContractStatus
from utils.enums import UnitStatus


class SignatureInput(forms.ClearableFileInput):
    """Use an uploaded file when present, otherwise preserve a canvas data URL."""

    def value_from_datadict(self, data, files, name):
        return files.get(name) or data.get(name)


class SignatureImageField(forms.ImageField):
    """Accept either an uploaded signature image or a PNG/JPEG data URL."""

    allowed_data_url_types = {"image/png": "png", "image/jpeg": "jpg"}

    widget = SignatureInput

    def to_python(self, data):
        if isinstance(data, str) and data.startswith("data:"):
            try:
                header, encoded_image = data.split(",", 1)
                content_type, encoding = header[5:].split(";", 1)
                extension = self.allowed_data_url_types[content_type]
                if encoding != "base64":
                    raise ValueError  # noqa: TRY301
                data = SimpleUploadedFile(
                    name=f"signature.{extension}",
                    content=base64.b64decode(encoded_image, validate=True),
                    content_type=content_type,
                )
            except KeyError, ValueError, binascii.Error:
                raise forms.ValidationError(
                    _("Submit a valid PNG or JPEG signature."),
                    code="invalid_signature",
                ) from None
        return super().to_python(data)


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

        self.fields["unit"].queryset = Unit.objects.select_related(
            "building", "building__property_ref__landlord"
        ).filter(
            status=UnitStatus.AVAILABLE,
            building__property_ref__status="ACTIVE",
            building__property_ref__tenant_management_enabled=True,
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
            raise forms.ValidationError(_("Rental duration must be at least 1 month."))
        return duration

    def clean_occupants_count(self):
        """Ensure there is at least one occupant."""
        occupants = self.cleaned_data["occupants_count"]
        if occupants is not None and occupants < 1:
            raise forms.ValidationError(_("There must be at least one occupant."))
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
                status=ApplicationStatus.PENDING,
            ).exists()
            if exists:
                raise forms.ValidationError(
                    _("You already have a pending application for this unit.")
                )

        return cleaned_data


class RentalContractForm(forms.ModelForm):
    """
    Form used by the landlord to create a rental contract.

    The tenant, unit, application and contract status are handled
    by the view/service layer.

    The landlord signature is uploaded from the signature canvas
    as an image file (PNG or JPEG).
    """

    monthly_rent = MoneyFormField(
        max_digits=12,
        decimal_places=2,
        required=True,
        label=_("Monthly rent"),
    )

    deposit = MoneyFormField(
        max_digits=12,
        decimal_places=2,
        required=True,
        label=_("Deposit"),
    )

    landlord_signature = SignatureImageField(
        required=True,
        label=_("Landlord signature"),
        help_text=_("Upload your handwritten signature (PNG or JPEG)."),
    )

    class Meta:
        model = RentalContract
        fields = (
            "start_date",
            "end_date",
            "monthly_rent",
            "deposit",
            "advance_rent_months",
            "landlord_signature",
        )

        widgets = {
            "start_date": forms.DateInput(
                attrs={"type": "date", "class": "form-input"}
            ),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "advance_rent_months": forms.NumberInput(
                attrs={"min": 1, "class": "form-input"}
            ),
        }

        labels = {
            "start_date": _("Start date"),
            "end_date": _("End date"),
            "advance_rent_months": _("Advance rent months"),
        }

        help_texts = {
            "end_date": _("Leave empty for an open-ended contract."),
            "advance_rent_months": _("Number of months paid in advance."),
        }

    # -------------------------------------------------------------------------
    # Field-level validation
    # -------------------------------------------------------------------------

    def clean_start_date(self):
        start_date = self.cleaned_data["start_date"]
        if start_date and start_date < timezone.now().date():
            raise forms.ValidationError(_("Start date cannot be in the past."))
        return start_date

    def clean_monthly_rent(self):
        rent = self.cleaned_data["monthly_rent"]
        if rent and rent.amount <= 0:
            raise forms.ValidationError(_("Monthly rent must be greater than zero."))
        return rent

    def clean_deposit(self):
        deposit = self.cleaned_data["deposit"]
        if deposit and deposit.amount < 0:
            raise forms.ValidationError(_("Deposit cannot be negative."))
        return deposit

    def clean_advance_rent_months(self):
        months = self.cleaned_data["advance_rent_months"]
        if months is not None and months < 1:
            raise forms.ValidationError(_("Advance rent must be at least one month."))
        return months

    # -------------------------------------------------------------------------
    # Cross-field validation
    # -------------------------------------------------------------------------

    def clean(self):
        cleaned_data = super().clean()

        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date <= start_date:
            self.add_error(
                "end_date",
                _("End date must be after the start date."),
            )

        return cleaned_data


class DirectRentalContractForm(RentalContractForm):
    """
    Form used by a landlord to create a rental contract directly.

    The tenant is searched dynamically by name, email or tenant ID.
    - If an existing tenant is selected → `tenant_id` is set.
    - If no tenant is found → the landlord can enter an email to invite
      the tenant directly in the same `tenant_search` field.

    The unit remains a standard ModelChoiceField limited to the
    landlord's available units.
    """

    tenant_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )

    tenant_search = forms.CharField(
        required=True,
        label=_("Tenant"),
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "autocomplete": "off",
                "placeholder": _("Search by name, email or tenant ID..."),
                "id": "tenant-search",
            }
        ),
    )

    unit = forms.ModelChoiceField(
        queryset=Unit.objects.none(),
        required=True,
        label=_("Unit"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, landlord, **kwargs):
        super().__init__(*args, **kwargs)

        self.landlord = landlord

        # Cached values populated during validation.
        self._tenant = None
        self._invite_email = None

        # Units: only available units belonging to this landlord.
        self.fields["unit"].queryset = (
            Unit.objects.select_related("building", "building__property_ref")
            .filter(
                building__property_ref__landlord=landlord,
                status=UnitStatus.AVAILABLE,
            )
            .order_by("building__building_number", "unit_number")
        )

    # -------------------------------------------------------------------------
    # Field-level validation
    # -------------------------------------------------------------------------

    def clean_tenant_id(self):
        """
        If a tenant_id is provided, validate it and cache the instance.
        """
        tenant_id = self.cleaned_data.get("tenant_id")
        if not tenant_id:
            return None

        try:
            tenant = Tenant.objects.select_related("user").get(
                pk=tenant_id, user__is_active=True
            )
        except Tenant.DoesNotExist:
            raise forms.ValidationError(
                _("The selected tenant does not exist.")
            ) from None

        self._tenant = tenant
        return tenant.pk

    def clean_tenant_search(self):
        """
        Validate the search field:
        - If a tenant_id is set → the search field is just a label, no further check.
        - Otherwise, the search value must be a valid email address for invitation.
        """
        value = self.cleaned_data["tenant_search"].strip()
        tenant_id = self.data.get("tenant_id")

        # If a tenant was selected, the search field just mirrors the choice.
        if tenant_id:
            return value

        # No tenant selected → the value must be a valid email to invite.
        if not value:
            raise forms.ValidationError(
                _("Please select a tenant or provide an email to invite.")
            )

        if "@" not in value:
            raise forms.ValidationError(
                _("No tenant found. To invite someone, enter their full email address.")
            )

        # Validate email format.
        try:
            validate_email(value)
        except DjangoValidationError:
            raise forms.ValidationError(
                _("Please enter a valid email address.")
            ) from None

        email = value.lower()

        # Reject if the email already belongs to an existing tenant.
        if Tenant.objects.filter(user__email__iexact=email).exists():
            raise forms.ValidationError(
                _(
                    "This email is already registered. "
                    "Please search and select the existing tenant."
                )
            )

        self._invite_email = email
        return value

    # -------------------------------------------------------------------------
    # Cross-field validation
    # -------------------------------------------------------------------------

    def clean(self):
        """
        Validate the tenant/unit combination and ensure the form is
        neither missing a tenant nor trying to do both select + invite.
        """
        cleaned_data = super().clean()

        tenant = self._tenant
        invite_email = self._invite_email
        unit = cleaned_data.get("unit")

        # ---- Exactly one of tenant / invite_email must be set. ----
        if not tenant and not invite_email:
            # The error is already on tenant_search.
            return cleaned_data

        if tenant and invite_email:
            self.add_error(
                "tenant_search",
                _("Please select an existing tenant OR invite a new one, not both."),
            )
            return cleaned_data

        # If no unit, we can't do further checks.
        if not unit:
            return cleaned_data

        # ---- Security: ensure unit belongs to landlord. ----
        if unit.building.property_ref.landlord_id != self.landlord.pk:
            self.add_error(
                "unit",
                _(
                    "You cannot create a contract for a unit that does not "
                    "belong to you."
                ),
            )
            return cleaned_data

        # ---- Prevent double active contract on the same unit. ----
        if RentalContract.objects.filter(
            unit=unit,
            status=ContractStatus.ACTIVE,
        ).exists():
            self.add_error(
                "unit",
                _("This unit already has an active contract."),
            )

        # ---- Final availability check. ----
        if unit.status != UnitStatus.AVAILABLE:
            self.add_error(
                "unit",
                _("This unit is no longer available."),
            )

        # ---- Only check tenant active contracts if an existing tenant was chosen. ----
        if (
            tenant
            and RentalContract.objects.filter(
                tenant=tenant,
                status=ContractStatus.ACTIVE,
            ).exists()
        ):
            self.add_error(
                "tenant_search",
                _("This tenant already has an active rental contract."),
            )

        return cleaned_data

    # -------------------------------------------------------------------------
    # Public helpers for the view
    # -------------------------------------------------------------------------

    def get_tenant(self):
        """Return the cached tenant instance, or None if inviting."""
        return self._tenant

    def get_invite_email(self):
        """Return the email to invite, or None if a tenant was selected."""
        return self._invite_email

    def is_inviting(self) -> bool:
        """Return True if the form is in 'invite a new tenant' mode."""
        return self._invite_email is not None


class TenantContractSignatureForm(forms.ModelForm):
    """
    Form used by the tenant to sign a rental contract.

    Contract terms are read-only for the tenant.
    Only the tenant signature is submitted here.
    """

    tenant_signature = SignatureImageField(
        required=True,
        label=_("Tenant signature"),
        help_text=_(
            "Sign the contract using your handwritten signature (PNG or JPEG)."
        ),
    )

    class Meta:
        model = RentalContract
        fields = ("tenant_signature",)

    # -------------------------------------------------------------------------
    # Cross-field validation
    # -------------------------------------------------------------------------

    def clean(self):
        """
        Ensure the contract is still in SIGNING status.

        Prevents signing a contract that is already ACTIVE, CANCELLED,
        or otherwise finalized.
        """
        cleaned_data = super().clean()

        if self.instance and self.instance.pk:
            if self.instance.status != ContractStatus.SIGNING:
                raise forms.ValidationError(
                    _("This contract is no longer awaiting your signature.")
                )

        return cleaned_data
