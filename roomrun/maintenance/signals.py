from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import generate_unique_identifier

from .models import MaintenanceRequest
from .models import Task


@receiver(pre_save, sender=MaintenanceRequest)
def set_request_number(sender, instance, **kwargs):
    """Auto-generate request_number if not already set."""
    if not instance.request_number:
        instance.request_number = generate_unique_identifier(
            prefix="MNT",
            model=MaintenanceRequest,
            field="request_number",
        )


@receiver(pre_save, sender=Task)
def set_task_number(sender, instance, **kwargs):
    """Auto-generate task_number if not already set."""
    if not instance.task_number:
        instance.task_number = generate_unique_identifier(
            prefix="TSK",
            model=Task,
            field="task_number",
        )
