from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("rentals", "0002_alter_rentalapplication_managers_and_more")]

    operations = [
        migrations.RemoveConstraint(
            model_name="rentalcontract",
            name="unique_active_contract_per_unit",
        ),
        migrations.AddConstraint(
            model_name="rentalcontract",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", ["SIGNING", "SIGNED", "ACTIVE"])),
                fields=("unit",),
                name="unique_open_contract_per_unit",
            ),
        ),
    ]
