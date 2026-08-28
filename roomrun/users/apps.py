from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
    verbose_name = _("Users")

    def ready(self):
        """
        Import signals to ensure they are registered with Django's signal
        dispatcher.
        """
        import users.signals  # noqa: F401, PLC0415
