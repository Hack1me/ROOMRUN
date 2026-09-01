import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [("users", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Otp",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, null=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created at")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated at")),
                ("is_deleted", models.BooleanField(default=False, db_index=True, help_text="Indicates whether this record has been soft-deleted.", verbose_name="Is deleted")),
                ("purpose", models.CharField(choices=[("signup", "Sign up"), ("login", "Sign in"), ("password_reset", "Password reset")], max_length=32, verbose_name="purpose")),
                ("code_hash", models.CharField(max_length=128, verbose_name="code hash")),
                ("expiration_at", models.DateTimeField(verbose_name="expires at")),
                ("attempts", models.PositiveSmallIntegerField(default=0, verbose_name="attempts")),
                ("is_used", models.BooleanField(default=False, verbose_name="used")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="otps", to=settings.AUTH_USER_MODEL, verbose_name="user")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL, verbose_name="Created by")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL, verbose_name="Updated by")),
            ],
            options={"db_table": "user_otps", "ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="otp", index=models.Index(fields=["user", "purpose", "is_used"], name="otp_user_purpose_idx")),
        migrations.AddIndex(model_name="otp", index=models.Index(fields=["expiration_at"], name="otp_expiration_idx")),
    ]
