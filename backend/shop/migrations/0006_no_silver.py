"""No silver (2026-10-21, from Amir): the client doesn't have the silver-white bag, so the colour goes, and the
specs list black and brown. Only where it is still as seeded (seed_store): a colour or spec the client set
in the panel is left alone. A silver order keeps its colour's name (Order.color_name), and the colour is only
hidden if an order points at it, as when it is deleted in the panel."""
from django.db import migrations

SILVER = ('سفید', 'images/colors/white.webp')
SPEC, OLD, NEW = 'رنگ', 'مشکی، قهوه‌ای، سفید', 'مشکی، قهوه‌ای'


def forwards(apps, schema_editor):
    Color, Product = apps.get_model('shop', 'Color'), apps.get_model('shop', 'Product')
    for color in Color.objects.filter(name=SILVER[0], photo=SILVER[1]):
        if color.orders.exists():
            color.shown = color.available = False
            color.save(update_fields=['shown', 'available'])
        else:
            color.delete()
    for product in Product.objects.all():
        specs = [[label, NEW] if [label, value] == [SPEC, OLD] else [label, value] for label, value in product.specs]
        if specs != product.specs:
            product.specs = specs
            product.save(update_fields=['specs'])


def backwards(apps, schema_editor):
    Color, Product = apps.get_model('shop', 'Color'), apps.get_model('shop', 'Product')
    for product in Product.objects.all():
        hidden = product.colors.filter(name=SILVER[0], photo=SILVER[1])
        if hidden.exists():
            hidden.update(shown=True, available=True)
        elif product.colors.exists():
            product.colors.create(name=SILVER[0], swatch='#b6babf', photo=SILVER[1], position=2)
        specs = [[label, OLD] if [label, value] == [SPEC, NEW] else [label, value] for label, value in product.specs]
        if specs != product.specs:
            product.specs = specs
            product.save(update_fields=['specs'])


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0005_brown_swatch'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
