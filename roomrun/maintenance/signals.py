from communications.services.notification_ser import send_notification
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from utils.enums import NotificationType
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


@receiver(pre_save, sender=MaintenanceRequest)
def capture_request_status(sender, instance, **kwargs):
    instance.notification_previous_status = None
    if instance.pk:
        instance.notification_previous_status = (
            sender.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )


@receiver(post_save, sender=MaintenanceRequest)
def notify_request_updates(sender, instance, created, **kwargs):
    property_ref = instance.unit.building.property_ref
    if created:
        send_notification(
            recipient=property_ref.landlord.user,
            title=_("New maintenance request"),
            message=_("%(tenant)s submitted a request: %(title)s.")
            % {"tenant": instance.tenant.user.full_name, "title": instance.title},
            notification_type=NotificationType.MAINTENANCE,
            related_object=instance,
        )
    elif instance.notification_previous_status != instance.status:
        send_notification(
            recipient=instance.tenant.user,
            title=_("Maintenance request updated"),
            message=_("Your request '%(title)s' is now %(status)s.")
            % {"title": instance.title, "status": instance.get_status_display()},
            notification_type=NotificationType.MAINTENANCE,
            related_object=instance,
        )
