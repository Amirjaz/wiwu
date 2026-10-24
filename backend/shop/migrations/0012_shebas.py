from django.db import migrations, models

# Amir, 2026-10-24: these two in place of the one in the store settings (his own, dropped).
SHEBAS = [
    ('IR970570022711517635897001', 'حسام منصوری', 'بانک پاسارگاد'),
    ('IR220610000007001005596838', 'محمدسالار کبیری', 'بانک شهر'),
]


def to_list(apps, schema_editor):
    """Amir's two Shebas; the one in the store settings is not carried over."""
    Sheba = apps.get_model('shop', 'Sheba')
    for position, (number, holder, bank) in enumerate(SHEBAS):
        if not Sheba.objects.filter(number=number).exists():
            Sheba.objects.create(number=number, holder=holder, bank=bank, position=position)


def to_one(apps, schema_editor):
    StoreSettings, Sheba = apps.get_model('shop', 'StoreSettings'), apps.get_model('shop', 'Sheba')
    first = Sheba.objects.filter(active=True).order_by('position', 'id').first()
    if first:
        StoreSettings.objects.filter(pk=1).update(sheba=first.number, sheba_holder=first.holder, sheba_bank=first.bank)


class Migration(migrations.Migration):
    """Several shop Shebas, every active one offered like the cards, in place of the one in the store settings."""

    dependencies = [
        ('shop', '0011_checkout_otp'),
    ]

    operations = [
        migrations.CreateModel(
            name='Sheba',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(max_length=26, verbose_name='شماره شبا')),
                ('holder', models.CharField(max_length=80, verbose_name='نام صاحب حساب')),
                ('bank', models.CharField(blank=True, max_length=40, verbose_name='بانک')),
                ('active', models.BooleanField(default=True, verbose_name='فعال')),
                ('position', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'شبا',
                'verbose_name_plural': 'شباها',
                'ordering': ['position', 'id'],
            },
        ),
        migrations.RunPython(to_list, to_one),
        migrations.RemoveField(model_name='storesettings', name='sheba'),
        migrations.RemoveField(model_name='storesettings', name='sheba_bank'),
        migrations.RemoveField(model_name='storesettings', name='sheba_holder'),
    ]
