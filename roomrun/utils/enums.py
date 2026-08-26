# enums.py
from django.db import models
from django.utils.translation import gettext_lazy as _


class EmployeeStatus(models.TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    INACTIVE = "INACTIVE", _("Inactive")
    SUSPENDED = "SUSPENDED", _("Suspended")


class GuardShift(models.TextChoices):
    DAY = "DAY", _("Day")
    NIGHT = "NIGHT", _("Night")
    ROTATING = "ROTATING", _("Rotating")
