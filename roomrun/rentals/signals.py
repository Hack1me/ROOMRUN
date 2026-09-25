from communications.services.notification_ser import send_notification
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from utils.enums import NotificationType
from utils.helpers import assign_reference_identifier

from .models import RentalApplication
from .models import RentalContract


@receiver(pre_save, sender=RentalApplication)
def set_application_number(sender, instance, **kwargs):
    """Auto-generate application_number if not already set."""
    assign_reference_identifier(instance, field="application_number", prefix="APP")


@receiver(pre_save, sender=RentalApplication)
def capture_application_status(sender, instance, **kwargs):
    instance.notification_previous_status = None
    if instance.pk:
        instance.notification_previous_status = (
            sender.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )


@receiver(post_save, sender=RentalApplication)
def notify_application_updates(sender, instance, created, **kwargs):
    property_ref = instance.unit.building.property_ref
    if created:
        send_notification(
            recipient=property_ref.landlord.user,
            title=_("New rental application"),
            message=_("%(tenant)s applied for unit %(unit)s at %(property)s.")
            % {
                "tenant": instance.tenant.user.full_name,
                "unit": instance.unit.unit_number,
                "property": property_ref.name,
            },
            notification_type=NotificationType.SYSTEM,
            related_object=instance,
        )
    elif instance.notification_previous_status != instance.status:
        send_notification(
            recipient=instance.tenant.user,
            title=_("Rental application updated"),
            message=_("Your application for %(property)s is now %(status)s.")
            % {
                "property": property_ref.name,
                "status": instance.get_status_display(),
            },
            notification_type=NotificationType.SYSTEM,
            related_object=instance,
        )


@receiver(pre_save, sender=RentalContract)
def set_contract_number(sender, instance, **kwargs):
    """Auto-generate contract_number if not already set."""

    assign_reference_identifier(instance, field="contract_number", prefix="CNT")


@receiver(pre_save, sender=RentalContract)
def capture_contract_status(sender, instance, **kwargs):
    instance.notification_previous_status = None
    if instance.pk:
        instance.notification_previous_status = (
            sender.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )


@receiver(post_save, sender=RentalContract)
def notify_contract_status(sender, instance, created, **kwargs):
    previous_status = getattr(instance, "notification_previous_status", None)
    property_ref = instance.unit.building.property_ref
    if created:
        send_notification(
            recipient=instance.tenant.user,
            title=_("Rental contract ready"),
            message=_("A rental contract for %(property)s is ready for your review.")
            % {"property": property_ref.name},
            notification_type=NotificationType.SYSTEM,
            related_object=instance,
        )
        return
    if previous_status == instance.status:
        return

    status_label = instance.get_status_display()
    send_notification(
        recipient=instance.tenant.user,
        title=_("Rental contract updated"),
        message=_("Your contract for %(property)s is now %(status)s.")
        % {"property": property_ref.name, "status": status_label},
        notification_type=NotificationType.SYSTEM,
        related_object=instance,
    )
    send_notification(
        recipient=property_ref.landlord.user,
        title=_("Rental contract updated"),
        message=_("The contract with %(tenant)s for %(property)s is now %(status)s.")
        % {
            "tenant": instance.tenant.user.full_name,
            "property": property_ref.name,
            "status": status_label,
        },
        notification_type=NotificationType.SYSTEM,
        related_object=instance,
    )
