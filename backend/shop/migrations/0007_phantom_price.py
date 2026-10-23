"""The two-zipper bag's price (2026-10-23, from Amir): 16,500,000 toman, in black and brown. seed_store added it
without one, which kept it off the site; with this it gets its section, its pictures and its checkout. Only
while it still has no price: one the client set in the panel stays."""
from django.db import migrations

SLUG, PRICE = 'phantom-pro', 165_000_000  # rials


def forwards(apps, schema_editor):
    apps.get_model('shop', 'Product').objects.filter(slug=SLUG, price_rial=0).update(price_rial=PRICE)


def backwards(apps, schema_editor):
    apps.get_model('shop', 'Product').objects.filter(slug=SLUG, price_rial=PRICE).update(price_rial=0)


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0006_no_silver'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
