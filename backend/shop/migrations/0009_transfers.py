import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Orders over the bank's per-transfer cap are paid in several transfers (Amir, 2026-10-24: 15M toman
    a transfer; the 16.5M two-zipper bag goes in 11.5M + 5M). See orders.split_amounts."""

    dependencies = [
        ('shop', '0008_cartbecart_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='transfer_limit_rial',
            field=models.PositiveBigIntegerField(default=150000000, verbose_name='سقف هر کارت‌به‌کارت (ریال)'),
        ),
        migrations.CreateModel(
            name='Transfer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveSmallIntegerField()),
                ('amount_rial', models.PositiveBigIntegerField(db_index=True)),
                ('offset_rial', models.PositiveBigIntegerField()),
                ('card_bank', models.CharField(max_length=40)),
                ('card_number', models.CharField(max_length=16)),
                ('card_holder', models.CharField(max_length=80)),
                ('expires_at', models.DateTimeField()),
                ('provider_token', models.CharField(blank=True, db_index=True, max_length=64)),
                ('provider_ref', models.CharField(blank=True, max_length=80)),
                ('status', models.CharField(choices=[('pending', 'در انتظار'), ('paid', 'رسید'), ('needs_review', 'بررسی'),
                                                     ('expired', 'منقضی'), ('cancelled', 'لغو')],
                                            default='pending', max_length=14)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('card', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                           related_name='+', to='shop.card')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transfers',
                                            to='shop.order')),
            ],
            options={
                'ordering': ['position'],
                'constraints': [models.UniqueConstraint(fields=('order', 'position'), name='transfer_position')],
            },
        ),
    ]
