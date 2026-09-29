from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("rentals", "0008_contractextensionrequest")]

    operations = [
        migrations.AddField(
            model_name="rentalcontract",
            name="existing_document",
            field=models.FileField(
                blank=True,
                help_text="Scanned copy of a contract signed outside the platform.",
                null=True,
                upload_to="contracts/existing/",
                verbose_name="Existing signed contract",
            ),
        ),
    ]
