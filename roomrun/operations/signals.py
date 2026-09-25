from communications.services.notification_ser import send_notification
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from rentals.models import RentalContract
from users.models import User
from utils.enums import CleaningStatus
from utils.enums import ContractStatus
from utils.enums import NotificationType
from utils.helpers import assign_reference_identifier

from .models import CleaningSchedule
from .models import UserInvitation
from .models import VisitorVisit


@receiver(pre_save, sender=CleaningSchedule)
def set_schedule_number(sender, instance, **kwargs):
    """Auto-generate schedule_number if not already set."""
    assign_reference_identifier(instance, field="schedule_number", prefix="CLS")


@receiver(pre_save, sender=CleaningSchedule)
def capture_cleaning_schedule_state(sender, instance, **kwargs):
    instance.notification_previous_state = None
    if instance.pk:
        instance.notification_previous_state = (
            sender.objects.filter(pk=instance.pk)
            .values("status", "scheduled_date")
            .first()
        )


@receiver(post_save, sender=CleaningSchedule)
def notify_cleaning_schedule(sender, instance, created, **kwargs):
    previous = getattr(instance, "notification_previous_state", None)
    rescheduled = bool(
        previous
        and previous["scheduled_date"] != instance.scheduled_date
        and instance.status == CleaningStatus.SCHEDULED
    )
    cancelled = bool(
        previous
        and previous["status"] != CleaningStatus.CANCELLED
        and instance.status == CleaningStatus.CANCELLED
    )
    if not created and not rescheduled and not cancelled:
        return

    tenant_ids = RentalContract.objects.filter(
        unit__building=instance.building,
        status__in=[ContractStatus.SIGNED, ContractStatus.ACTIVE],
    ).values_list("tenant__user_id", flat=True).distinct()
    title = (
        _("Cleaning scheduled") if created else
        _("Cleaning schedule updated") if rescheduled else
        _("Cleaning schedule cancelled")
    )
    message_template = (
        _("Cleaning is planned for %(date)s at %(building)s.")
        if created or rescheduled
        else _("The cleaning scheduled for %(date)s at %(building)s was cancelled.")
    )
    message = message_template % {
        "date": instance.scheduled_date.strftime("%d/%m/%Y"),
        "building": instance.building.name,
    }
    for user in User.objects.filter(pk__in=tenant_ids):
        send_notification(
            recipient=user,
            title=title,
            message=message,
            notification_type=NotificationType.SYSTEM,
            related_object=instance,
        )


@receiver(pre_save, sender=VisitorVisit)
def capture_visitor_status(sender, instance, **kwargs):
    instance.notification_previous_status = None
    if instance.pk:
        instance.notification_previous_status = (
            sender.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )


@receiver(post_save, sender=VisitorVisit)
def notify_visitor_check_in(sender, instance, created, **kwargs):
    if (
        not created
        and instance.host_id
        and instance.status == "CHECKED_IN"
        and instance.notification_previous_status != instance.status
    ):
        send_notification(
            recipient=instance.host,
            title=_("Your visitor has arrived"),
            message=_("%(visitor)s checked in at %(building)s.")
            % {"visitor": instance.visitor_name, "building": instance.building.name},
            notification_type=NotificationType.SYSTEM,
            related_object=instance,
        )


@receiver(pre_save, sender=UserInvitation)
def capture_invitation_status(sender, instance, **kwargs):
    instance.notification_previous_status = None
    if instance.pk:
        instance.notification_previous_status = (
            sender.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )


@receiver(post_save, sender=UserInvitation)
def notify_invitation_accepted(sender, instance, created, **kwargs):
    if (
        not created
        and instance.status == "ACCEPTED"
        and instance.notification_previous_status != instance.status
    ):
        send_notification(
            recipient=instance.invited_by,
            title=_("Invitation accepted"),
            message=_("%(email)s accepted your invitation to join ROOMRUN.")
            % {"email": instance.email},
            notification_type=NotificationType.SYSTEM,
            related_object=instance,
        )
