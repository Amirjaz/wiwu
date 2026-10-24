from django.db import migrations, models


class Migration(migrations.Migration):
    """Orders registered with cartbecart keep their payment_token (see shop/payments.py)."""

    dependencies = [
        ('shop', '0007_phantom_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='provider_token',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
    ]
