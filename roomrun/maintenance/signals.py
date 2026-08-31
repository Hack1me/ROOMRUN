from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import assign_reference_identifier

from .models import MaintenanceRequest
from .models import Task


@receiver(pre_save, sender=MaintenanceRequest)
def set_request_number(sender, instance, **kwargs):
    """Auto-generate request_number if not already set."""
    assign_reference_identifier(instance, field="request_number", prefix="MNT")


@receiver(pre_save, sender=Task)
def set_task_number(sender, instance, **kwargs):
    """Auto-generate task_number if not already set."""
    assign_reference_identifier(instance, field="task_number", prefix="TSK")
