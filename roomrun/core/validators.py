import os

import phonenumbers
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_phone_number(value):
    """
    Validate that the given phone number is both valid and possible
    according to the global phonenumbers library.
    This works with any string representation (international format preferred).
    """
    try:
        # Parse the number assuming it might be international
        parsed = phonenumbers.parse(value, None)
    except phonenumbers.NumberParseException:
        raise ValidationError(  # noqa: B904
            _(
                "Invalid phone number format. Use international format, "
                "e.g. +33123456789."
            ),
            code="invalid_phone",
        )

    # Check if the number is valid and possible
    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError(
            _("The phone number is not valid for the selected country."),
            code="invalid_phone",
        )

    if not phonenumbers.is_possible_number(parsed):
        raise ValidationError(
            _("The phone number is too long or too short."),
            code="impossible_phone",
        )


def validate_phone_number_for_country(value, country_code="FR"):
    """
    Validate that the phone number is valid for a specific country.
    `country_code` should be a two-letter ISO country code (e.g., "FR", "US").
    """
    # django-phonenumber-field may pass a PhoneNumber object rather than its
    # textual representation when this validator runs from a form.
    value = str(value)
    try:
        parsed = phonenumbers.parse(value, country_code)
    except phonenumbers.NumberParseException:
        raise ValidationError(  # noqa: B904
            _("Invalid phone number for %(country)s."),
            params={"country": country_code},
            code="invalid_phone",
        )

    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError(
            _("The phone number is not valid for %(country)s."),
            params={"country": country_code},
            code="invalid_phone",
        )


def validate_phone_number_with_region(value, expected_region="FR"):
    """
    Validate that the phone number belongs to a specific region.
    Raises a validation error if the number's country code does not match
    the expected region.
    """
    try:
        parsed = phonenumbers.parse(value, None)
    except phonenumbers.NumberParseException:
        raise ValidationError(_("Invalid phone number format."))  # noqa: B904

    region = phonenumbers.region_code_for_number(parsed)
    if region != expected_region:
        raise ValidationError(
            _("The phone number must be from %(region)s."),
            params={"region": expected_region},
            code="wrong_region",
        )


# ---------___________----------
# ----- IMAGES VALIDATORS----
# ---------___________----------


def validate_image_size(value):
    """
    Ensure the uploaded image does not exceed 5 MB.
    """
    max_size = 5 * 1024 * 1024  # 5 MB
    if value.size > max_size:
        raise ValidationError(
            _("The image size must not exceed %(max_size)d MB."),
            params={"max_size": 5},
            code="image_too_large",
        )


def validate_image_extension(value):
    """
    Restrict allowed image file extensions.
    """
    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    ext = os.path.splitext(value.name)[1].lower()  # noqa: PTH122
    if ext not in allowed_extensions:
        raise ValidationError(
            _("Allowed image formats are: JPG, JPEG, PNG, and WEBP."),
            code="invalid_extension",
        )


def validate_image_dimensions(value):
    """
    (Optional) Enforce minimum width and height for uploaded images.
    Requires Pillow.
    """
    from PIL import Image  # noqa: PLC0415

    try:
        img = Image.open(value)
        width, height = img.size
        min_width, min_height = 800, 600  # Example minimum
        if width < min_width or height < min_height:
            raise ValidationError(  # noqa: TRY301
                _("Image must be at least %(width)d x %(height)d pixels."),
                params={"width": min_width, "height": min_height},
                code="image_too_small",
            )
    except Exception:  # noqa: BLE001, S110
        # Ignore PIL errors (e.g., corrupt files) validation will pass
        pass
