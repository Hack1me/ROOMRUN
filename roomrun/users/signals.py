# users/signals.py

import uuid
from typing import Type
from typing import TypeVar

from django.db.models import Model
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Employee
from .models import Guard
from .models import Landlord
from .models import MaintenanceAgent
from .models import Tenant

# Type variable for the model class
M = TypeVar("M", bound=Model)


def generate_unique_identifier(prefix: str, model: Type[M], field: str = "id") -> str:
    """
    Generate a unique alphanumeric identifier with a given prefix.

    The identifier format is: {PREFIX}-{8-character-UUID}
    Example: LND-A7F9B3C1

    This function loops until a unique identifier is found, making it safe
    for concurrent use, although collisions are extremely unlikely.

    Args:
        prefix: The uppercase prefix for the identifier (e.g., 'LND', 'TEN').
        model: The Django model class to check against.
        field: The model field name that stores the identifier.

    Returns:
        A unique identifier string.
    """
    while True:
        identifier = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
        kwargs = {field: identifier}
        if not model.objects.filter(**kwargs).exists():
            return identifier


# ===========================================================================
# LANDLORD SIGNAL
# ===========================================================================
@receiver(pre_save, sender=Landlord)
def set_landlord_number(sender, instance: Landlord, **kwargs) -> None:
    """
    Auto-generate landlord_number if not already set.
    """
    if not instance.landlord_number:
        instance.landlord_number = generate_unique_identifier(
            prefix="LND",
            model=Landlord,
            field="landlord_number",
        )


# ===========================================================================
# TENANT SIGNAL
# ===========================================================================
@receiver(pre_save, sender=Tenant)
def set_tenant_number(sender, instance: Tenant, **kwargs) -> None:
    """
    Auto-generate tenant_number if not already set.
    """
    if not instance.tenant_number:
        instance.tenant_number = generate_unique_identifier(
            prefix="TEN",
            model=Tenant,
            field="tenant_number",
        )


# ===========================================================================
# EMPLOYEE SIGNAL
# ===========================================================================
@receiver(pre_save, sender=Employee)
def set_employee_number(sender, instance: Employee, **kwargs) -> None:
    """
    Auto-generate employee_number if not already set.
    """
    if not instance.employee_number:
        instance.employee_number = generate_unique_identifier(
            prefix="EMP",
            model=Employee,
            field="employee_number",
        )


# ===========================================================================
# MAINTENANCE AGENT SIGNAL
# ===========================================================================
@receiver(pre_save, sender=MaintenanceAgent)
def set_agent_number(sender, instance: MaintenanceAgent, **kwargs) -> None:
    """
    Auto-generate agent_number if not already set.
    """
    if not instance.agent_number:
        instance.agent_number = generate_unique_identifier(
            prefix="M-AG",
            model=MaintenanceAgent,
            field="agent_number",
        )


# ===========================================================================
# GUARD SIGNAL
# ===========================================================================
@receiver(pre_save, sender=Guard)
def set_guard_number(sender, instance: Guard, **kwargs) -> None:
    """
    Auto-generate guard_number if not already set.
    """
    if not instance.guard_number:
        instance.guard_number = generate_unique_identifier(
            prefix="GRD",
            model=Guard,
            field="guard_number",
        )
