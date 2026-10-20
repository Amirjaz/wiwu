"""The brown is WiWU's coffee brown (2026-10-20): the hero's posters and the colour pictures now come from
WiWU's own brown render (tools/hero_slides.py, tools/color_photos.py), darker than the reseller's photo the
first swatch was taken from. The dot, and the 3D bag's tint, follow it where the swatch is still the first
one; a swatch the client set in the panel stays."""
from django.db import migrations

OLD, NEW = '#b9683f', '#463930'


def forwards(apps, schema_editor):
    apps.get_model('shop', 'Color').objects.filter(swatch=OLD).update(swatch=NEW)


def backwards(apps, schema_editor):
    apps.get_model('shop', 'Color').objects.filter(swatch=NEW).update(swatch=OLD)


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0004_client_answers'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
