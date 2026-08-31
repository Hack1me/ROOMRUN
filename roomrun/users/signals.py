from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import assign_reference_identifier

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
    assign_reference_identifier(instance, field="landlord_number", prefix="LND")


# ===========================================================================
# TENANT SIGNAL
# ===========================================================================
@receiver(pre_save, sender=Tenant)
def set_tenant_number(sender, instance: Tenant, **kwargs) -> None:
    """
    Auto-generate tenant_number if not already set.
    """
    assign_reference_identifier(instance, field="tenant_number", prefix="TEN")


# ===========================================================================
# EMPLOYEE SIGNAL
# ===========================================================================
@receiver(pre_save, sender=Employee)
def set_employee_number(sender, instance: Employee, **kwargs) -> None:
    """
    Auto-generate employee_number if not already set.
    """
    assign_reference_identifier(instance, field="employee_number", prefix="EMP")


# ===========================================================================
# MAINTENANCE AGENT SIGNAL
# ===========================================================================
@receiver(pre_save, sender=MaintenanceAgent)
def set_agent_number(sender, instance: MaintenanceAgent, **kwargs) -> None:
    """
    Auto-generate agent_number if not already set.
    """
    assign_reference_identifier(instance, field="agent_number", prefix="M-AG")


# ===========================================================================
# GUARD SIGNAL
# ===========================================================================
@receiver(pre_save, sender=Guard)
def set_guard_number(sender, instance: Guard, **kwargs) -> None:
    """
    Auto-generate guard_number if not already set.
    """
    assign_reference_identifier(instance, field="guard_number", prefix="GRD")
