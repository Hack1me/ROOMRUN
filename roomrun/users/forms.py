from core.validators import validate_phone_number_for_country
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth import forms as admin_forms
from django.contrib.auth.password_validation import validate_password
from django.forms import EmailField
from django.utils.translation import gettext_lazy as _
from django_countries.widgets import CountrySelectWidget
from phonenumber_field.formfields import PhoneNumberField

from .mixins import NormalizedEmailMixin
from .mixins import PasswordConfirmMixin
from .models import User


class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):
        model = User
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.AdminUserCreationForm):
    """
    Form for User Creation in the Admin Area.
    """

    class Meta(admin_forms.UserCreationForm.Meta):
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


class SigninForm(forms.Form):
    email = forms.EmailField(label=_("Email address"))
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput,
    )
    remember_me = forms.BooleanField(label=_("Keep me signed in"), required=False)

    user = None

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")
        if not email or not password:
            return cleaned_data

        self.user = authenticate(email=email, password=password)
        if self.user is None:
            raise forms.ValidationError(_("Incorrect email address or password."))
        if not self.user.is_active or not self.user.is_active_user():
            raise forms.ValidationError(_("This account is disabled."))
        return cleaned_data


class SignupForm(NormalizedEmailMixin, PasswordConfirmMixin, forms.ModelForm):
    ROLE_CHOICES = [
        ("tenant", _("Tenant")),
        ("landlord", _("Landlord")),
    ]
    role = forms.ChoiceField(
        label=_("Profile type"),
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(
            attrs={
                "class": "sr-only",
            }
        ),
    )
    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": (
                    "h-11 w-full rounded-input border border-line bg-white py-2 "
                    "pl-9 pr-11 text-sm text-ink outline-none transition "
                    "placeholder:text-muted/70 focus:border-secondary "
                    "focus:ring-3 focus:ring-secondary/15"
                ),
                "placeholder": "••••••••",
                "autocomplete": "new-password",
            }
        ),
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": (
                    "h-11 w-full rounded-input border border-line bg-white py-2 "
                    "pl-9 pr-3 text-sm text-ink outline-none transition "
                    "placeholder:text-muted/70 focus:border-secondary "
                    "focus:ring-3 focus:ring-secondary/15"
                ),
                "placeholder": "••••••••",
                "autocomplete": "new-password",
            }
        ),
    )
    accept_terms = forms.BooleanField(
        label=_("I accept the terms and conditions"),
        required=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "mt-0.5 size-[18px] shrink-0 cursor-pointer"
                "rounded border-2 border-line text-primary accent-primary"
                "focus:ring-3 focus:ring-secondary/20",
            }
        ),
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
            "accept_terms",
        )
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": (
                        "h-11 w-full rounded-input border border-line bg-white py-2 "
                        "pl-9 pr-3 text-sm text-ink outline-none transition "
                        "placeholder:text-muted/70 focus:border-secondary "
                        "focus:ring-3 focus:ring-secondary/15"
                    ),
                    "placeholder": _("Sahit"),
                    "autocomplete": "given-name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": (
                        "h-11 w-full rounded-input border border-line bg-white px-3 "
                        "py-2 text-sm text-ink outline-none transition "
                        "placeholder:text-muted/70 focus:border-secondary "
                        "focus:ring-3 focus:ring-secondary/15"
                    ),
                    "placeholder": _("Heufeu"),
                    "autocomplete": "family-name",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": (
                        "h-11 w-full rounded-input border border-line bg-white py-2 "
                        "pl-9 pr-3 text-sm text-ink outline-none transition "
                        "placeholder:text-muted/70 focus:border-secondary "
                        "focus:ring-3 focus:ring-secondary/15"
                    ),
                    "placeholder": _("you@example.com"),
                    "autocomplete": "email",
                }
            ),
        }

    def clean_email(self):
        email = super().clean_email()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                _("An account already exists with this email address.")
            )
        return email

    def save(self, *, commit=True):
        user = super().save(commit=False)
        user.email = user.email.lower().strip()
        user.email_verified = False
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ForgotPasswordForm(NormalizedEmailMixin, forms.Form):
    email = forms.EmailField(label=_("Email address"))


class OtpVerificationForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput)
    code = forms.CharField(label=_("Verification code"), min_length=6, max_length=6)

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError(_("Enter the six-digit code sent by email."))
        return code


class PasswordResetConfirmForm(PasswordConfirmMixin, forms.Form):
    token = forms.CharField(widget=forms.HiddenInput)
    password1 = forms.CharField(
        label=_("New password"), strip=False, widget=forms.PasswordInput
    )
    password2 = forms.CharField(
        label=_("Password confirmation"), strip=False, widget=forms.PasswordInput
    )

# User Profile form
class ProfileForm(forms.ModelForm):
    """
    Form used to update the authenticated user's profile.
    """

    # Override phone field to add the validator
    phone = PhoneNumberField(
        validators=[validate_phone_number_for_country],
        required=False,
        widget=forms.TextInput(attrs={
            "autocomplete": "tel",
            "placeholder": _("+33123456789"),
        }),
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "phone",
            "country",
            "profile_picture",
        )

        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel"}),
            "country": CountrySelectWidget(
                attrs={"autocomplete": "country", "class": "rr-input"}
            ),
            "profile_picture": forms.FileInput(attrs={"accept": "image/*"}),
        }

        labels = {
            "first_name": _("First name"),
            "last_name": _("Last name"),
            "phone": _("Phone number"),
            "country": _("Country"),
            "profile_picture": _("Profile picture"),
        }

        help_texts = {
            "phone": _("International format, e.g. +33123456789."),
            "profile_picture": _("Upload a JPG, PNG, or WebP image. Max size: 5 MB."),
        }



class TenantInvitationAcceptForm(forms.Form):
    """
    Form used by an invited user to set up their account
    (name + password) after clicking an invitation link.
    """

    first_name = forms.CharField(
        max_length=150,
        label=_("First name"),
        widget=forms.TextInput(attrs={"class": "form-input", "autocomplete": "given-name"}),
    )

    last_name = forms.CharField(
        max_length=150,
        label=_("Last name"),
        widget=forms.TextInput(attrs={"class": "form-input", "autocomplete": "family-name"}),
    )

    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={"class": "form-input", "autocomplete": "new-password"}),
        help_text=_(
            "At least 8 characters, not entirely numeric, and not a common password."
        ),
    )

    password_confirm = forms.CharField(
        label=_("Confirm password"),
        widget=forms.PasswordInput(attrs={"class": "form-input", "autocomplete": "new-password"}),
    )

    # -------------------------------------------------------------------------
    # Field-level validation
    # -------------------------------------------------------------------------

    def clean_first_name(self):
        """Strip and validate the first name."""
        first_name = self.cleaned_data["first_name"].strip()
        if not first_name:
            raise forms.ValidationError(_("First name cannot be empty."))
        return first_name

    def clean_last_name(self):
        """Strip and validate the last name."""
        last_name = self.cleaned_data["last_name"].strip()
        if not last_name:
            raise forms.ValidationError(_("Last name cannot be empty."))
        return last_name

    def clean_password(self):
        """
        Run Django's configured password validators.
        """
        password = self.cleaned_data["password"]
        # validate_password raises ValidationError if the password is weak.
        validate_password(password)
        return password

    # -------------------------------------------------------------------------
    # Cross-field validation
    # -------------------------------------------------------------------------

    def clean(self):
        """Ensure the two password fields match."""
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error(
                "password_confirm",
                _("Passwords do not match."),
            )

        return cleaned_data
