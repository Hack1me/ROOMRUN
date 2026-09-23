import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("billing", "0003_remove_payment_transaction_reference_and_more")]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="external_reference",
            field=models.CharField(
                default=uuid.uuid4,
                editable=False,
                help_text="Unique reference used to identify this payment externally.",
                max_length=100,
                unique=True,
                verbose_name="External reference",
            ),
        ),
    ]
