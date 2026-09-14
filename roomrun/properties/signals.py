from django.db.models.signals import post_delete
from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import assign_reference_identifier

from .models import Building
from .models import Property
from .models import PropertyImage
from .models import Unit


@receiver(pre_save, sender=Property)
def set_property_number(sender, instance, **kwargs):
    """Auto-generate property_number if not already set."""
    assign_reference_identifier(instance, field="property_number", prefix="PRP")


@receiver(pre_save, sender=Building)
def set_building_number(sender, instance, **kwargs):
    """Auto-generate building_number if not already set."""
    assign_reference_identifier(instance, field="building_number", prefix="BLD")


@receiver(pre_save, sender=Unit)
def set_unit_number(sender, instance, **kwargs):
    """Auto-generate unit_number if not already set."""
    assign_reference_identifier(instance, field="unit_number", prefix="UNT")

# PROPERTY IMAGE
@receiver(pre_save, sender=PropertyImage)
def ensure_single_primary_image(sender, instance, **kwargs):
    """
    When an image is marked as primary, unset the primary flag on all
    other images belonging to the same property or unit.
    """
    if instance.is_primary:
        if instance.property_id:
            siblings = PropertyImage.objects.filter(property_id=instance.property_id)
        else:
            siblings = PropertyImage.objects.filter(unit_id=instance.unit_id)
        siblings.exclude(pk=instance.pk).update(is_primary=False)


@receiver(post_delete, sender=PropertyImage)
def delete_property_image_file(sender, instance, **kwargs):
    """
    Delete the physical image file from storage when the database record
    is deleted.
    """
    if instance.image:
        try:  # noqa: SIM105
            instance.image.delete(save=False)
        except Exception:  # noqa: BLE001, S110
            # Silently ignore file deletion errors to avoid breaking the transaction
            pass
