from django.db.models.signals import post_delete
from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import generate_unique_identifier

from .models import Building
from .models import Property
from .models import PropertyImage


@receiver(pre_save, sender=Property)
def set_property_number(sender, instance, **kwargs):
    """Auto-generate property_number if not already set."""
    if not instance.property_number:
        instance.property_number = generate_unique_identifier(
            prefix="PRP",
            model=Property,
            field="property_number",
        )

@receiver(pre_save, sender=Building)
def set_building_number(sender, instance, **kwargs):
    """Auto-generate building_number if not already set."""
    if not instance.building_number:
        instance.building_number = generate_unique_identifier(
            prefix="BLD",
            model=Building,
            field="building_number",
        )

# PROPERTY IMAGE
@receiver(pre_save, sender=PropertyImage)
def ensure_single_primary_image(sender, instance, **kwargs):
    """
    When an image is marked as primary, unset the primary flag on all
    other images belonging to the same property.
    """
    if instance.is_primary:
        PropertyImage.objects.filter(
            property=instance.property, is_primary=True
        ).exclude(pk=instance.pk).update(is_primary=False)


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
