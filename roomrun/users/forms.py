from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth import forms as admin_forms
from django.contrib.auth.password_validation import validate_password
from django.forms import EmailField
from django.utils.translation import gettext_lazy as _

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


class SignupForm(forms.ModelForm):
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
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                _("An account already exists with this email address.")
            )
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", _("The passwords do not match."))
        if password1:
            try:
                validate_password(password1)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data

    def save(self, *, commit=True):
        user = super().save(commit=False)
        user.email = user.email.lower().strip()
        user.email_verified = False
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(label=_("Email address"))

    def clean_email(self):
        return self.cleaned_data["email"].lower().strip()


class OtpVerificationForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput)
    code = forms.CharField(label=_("Verification code"), min_length=6, max_length=6)

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError(_("Enter the six-digit code sent by email."))
        return code


class PasswordResetConfirmForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput)
    password1 = forms.CharField(
        label=_("New password"), strip=False, widget=forms.PasswordInput
    )
    password2 = forms.CharField(
        label=_("Password confirmation"), strip=False, widget=forms.PasswordInput
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", _("The passwords do not match."))
        if password1:
            try:
                validate_password(password1)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data
