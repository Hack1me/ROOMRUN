from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0003_alter_employee_user_alter_guard_employee_and_more")]

    operations = [
        migrations.AddField(
            model_name="maintenanceagent",
            name="landlords",
            field=models.ManyToManyField(
                blank=True,
                help_text="Landlords who can assign this maintenance agent.",
                related_name="maintenance_agents",
                to="users.landlord",
                verbose_name="Landlords",
            ),
        ),
    ]
