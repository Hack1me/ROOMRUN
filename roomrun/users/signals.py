from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import generate_unique_identifier

from .models import Employee
from .models import Guard
from .models import Landlord
from .models import MaintenanceAgent
from .models import Tenant


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
