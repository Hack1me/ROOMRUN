from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PropertiesConfig(AppConfig):
    """
    App configuration for the properties module.
    Registers signals and sets application metadata.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "properties"
    verbose_name = _("Properties")

    def ready(self) -> None:
        """
        Called when Django fully loads the app registry.
        Imports signals to register pre_save receivers for auto-generation
        of property numbers.
        """
        import properties.signals  # noqa: F401, PLC0415
