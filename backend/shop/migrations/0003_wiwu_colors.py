"""The bag is WiWU's (ویوو) Alpha, and it comes in brown and silver-white too (2026-10-19, from Amir).

Adds the two colours, on show and in stock (their swatches are the leather's colour on the maker's photos;
the 3D bag takes its tint from them), gives each colour its photo (tools/studio_images.py), and names the
brand where the starting text is still as seeded. Text the client changed in the panel is left alone."""
from django.db import migrations, models

OLD_NAME = 'کیف دستی آلفا با قفل اثر انگشت'
NEW_NAME = 'کیف دستی ویوو آلفا با قفل اثر انگشت'
COLORS = [('قهوه‌ای', '#b9683f'), ('سفید', '#b6babf')]
PHOTOS = {'مشکی': 'images/colors/black.webp', 'قهوه‌ای': 'images/colors/brown.webp', 'سفید': 'images/colors/white.webp'}
SPECS = {
    ('رنگ', 'مشکی'): ('رنگ', 'مشکی، قهوه‌ای، سفید'),
    ('برند', 'WiWU (وارداتی)'): ('برند', 'ویوو (WiWU)، وارداتی'),
}


def forwards(apps, schema_editor):
    Product, Color, Page = apps.get_model('shop', 'Product'), apps.get_model('shop', 'Color'), apps.get_model('shop', 'Page')
    for product in Product.objects.all():
        last = max((c.position for c in Color.objects.filter(product=product)), default=0)
        for i, (name, swatch) in enumerate(COLORS, start=1):
            Color.objects.get_or_create(product=product, name=name,
                                        defaults={'swatch': swatch, 'position': last + i})
        for color in Color.objects.filter(product=product, name__in=PHOTOS, photo=''):
            color.photo = PHOTOS[color.name]
            color.save()
        changed = False
        if product.name == OLD_NAME:
            product.name, changed = NEW_NAME, True
        if product.description.startswith('آلفا کیف دستی'):
            product.description, changed = 'ویوو آلفا' + product.description[len('آلفا'):], True
        specs = [list(SPECS.get(tuple(pair), pair)) for pair in product.specs]
        if specs != product.specs:
            product.specs, changed = specs, True
        if changed:
            product.save()
    for page in Page.objects.filter(body__contains=OLD_NAME):
        page.body = page.body.replace(OLD_NAME, NEW_NAME)
        page.save()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0002_colors'),
    ]

    operations = [
        migrations.AddField(
            model_name='color',
            name='photo',
            field=models.CharField(blank=True, help_text='عکس کیف در این رنگ، از پوشه‌ی تصاویر سایت، مثل images/colors/brown.webp', max_length=120, verbose_name='عکس'),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
