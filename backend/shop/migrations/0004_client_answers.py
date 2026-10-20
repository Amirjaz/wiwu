"""The client's answers (2026-10-20, from Amir): the shop is called WiWU (ویوو); the bag costs 14,100,000 toman,
its shipping from Dubai included; the post is free and Tipax is paid by the buyer when it arrives (پس‌کرایه),
4 to 6 working days either way; a full charge takes 5 to 10 minutes and lasts about a month (a power bank
will do); 72 hours' replacement warranty if the lock or the zipper fails, the shop paying the shipping.

Adds the switch for Tipax paid on delivery (copied onto each order, like its fee), then updates the starting
content wherever it is still as seeded (seed_store): what the client changed in the panel is left alone."""
from django.db import migrations, models

OLD_PRICE, NEW_PRICE = 100_000_000, 141_000_000  # rials
PLACEHOLDER_FEES = (1_200_000, 2_500_000)  # post, Tipax (seed_store's placeholders)
DAYS = {'۲ تا ۴ روز کاری': '۴ تا ۶ روز کاری', '۱ تا ۳ روز کاری': '۴ تا ۶ روز کاری'}

OLD_CHARGE = ['شارژ قفل', 'باتری قابل شارژ با درگاه USB-C']
NEW_CHARGE = [['شارژ قفل', 'USB-C، شارژ کامل در ۵ تا ۱۰ دقیقه'],
              ['باتری', 'حدود یک ماه با هر شارژ؛ با پاوربانک هم شارژ می‌شود']]
WARRANTY_SPEC = ['گارانتی', '۷۲ ساعت تعویض، اگر قفل یا زیپ مشکل داشته باشد']

FAQ = {
    'سفارش کی به دستم می‌رسد؟': (
        'سفارش‌ها در روزهای کاری آماده و ارسال می‌شوند. زمان رسیدن با پست پیشتاز و تیپاکس در صفحه خرید نوشته شده و '
        'کد رهگیری مرسوله را پیامک می‌کنیم.',
        'سفارش‌ها در روزهای کاری آماده و ارسال می‌شوند و **۴ تا ۶ روز کاری** بعد به دستتان می‌رسند. ارسال با پست '
        'پیشتاز **رایگان** است؛ اگر تیپاکس را انتخاب کنید، هزینه‌اش را هنگام تحویل به تیپاکس می‌پردازید (پس‌کرایه). '
        'کد رهگیری مرسوله را پیامک می‌کنیم.'),
    'اگر شارژ قفل تمام شود چه می‌شود؟': (
        'قفل با کابل USB-C شارژ می‌شود. [اینکه با باتری خالی کیف چطور باز می‌شود را کارفرما از روی کالا تأیید کند.]',
        'قفل با کابل USB-C شارژ می‌شود و شارژ کاملش فقط **۵ تا ۱۰ دقیقه** طول می‌کشد؛ با هر بار شارژ حدود '
        '**یک ماه** کار می‌کند. اگر شارژ تمام شد، کافی است کیف را چند دقیقه به پاوربانک، شارژر گوشی یا لپ‌تاپ وصل کنید.'),
    'کالا گارانتی دارد؟': (
        'کالا وارداتی است و گارانتی آن را فروشگاه می‌دهد: [مدت و شرایط گارانتی را کارفرما تعیین کند].',
        'بله، **۷۲ ساعت گارانتی تعویض**. اگر در ۷۲ ساعت پس از تحویل، قفل اثر انگشت کار نکرد یا زیپ گیر کرد، کیف را '
        'با یک کیف سالم عوض می‌کنیم و هزینه ارسال آن با ماست.'),
}

WARRANTY_PAGE = (
    'کیف ویوو آلفا **۷۲ ساعت گارانتی تعویض** دارد، از زمانی که کیف به دستتان می‌رسد.\n\n'
    '## چه چیزهایی را پوشش می‌دهد\n'
    '- قفل اثر انگشت کار نکند یا اثر انگشت ثبت‌شده را نشناسد.\n'
    '- زیپ گیر کند یا باز و بسته نشود.\n\n'
    '## چطور از آن استفاده کنم\n'
    '- در همان ۷۲ ساعت با ما تماس بگیرید (راه‌های تماس در پایین همه صفحه‌ها آمده است) و کد سفارش را بگویید.\n'
    '- کیف را برایمان بفرستید؛ **هزینه ارسال رفت و برگشت با فروشگاه است**.\n'
    '- پس از بررسی، یک کیف سالم به جای آن برایتان فرستاده می‌شود.')
SHIPPING_PAGE = (
    'سفارش‌ها در روزهای کاری آماده و ارسال می‌شوند و **۴ تا ۶ روز کاری** بعد به دستتان می‌رسند. قیمت کیف شامل '
    'هزینه حمل آن از دبی است.\n\n'
    '## روش‌های ارسال\n'
    '- **پست پیشتاز:** رایگان.\n'
    '- **تیپاکس:** پس‌کرایه؛ هزینه را هنگام تحویل به تیپاکس می‌پردازید.\n\n'
    'کد رهگیری مرسوله پس از ارسال برای شما پیامک می‌شود.\n\n'
    'اگر سفارش را هدیه می‌دهید، گزینه «هدیه است» را بزنید تا فاکتور با قیمت داخل بسته گذاشته نشود.')
OLD_SHIPPING_START = 'سفارش‌ها در روزهای کاری آماده و با پست پیشتاز یا تیپاکس ارسال می‌شوند.'
TERMS = [
    ('- قیمت‌ها به تومان و شامل همه هزینه‌ها جز هزینه ارسال است که پیش از پرداخت نمایش داده می‌شود.',
     '- قیمت‌ها به تومان و شامل همه هزینه‌ها، از جمله حمل کالا از دبی، است. ارسال با پست پیشتاز رایگان است و '
     'هزینه تیپاکس را خریدار هنگام تحویل می‌پردازد (پس‌کرایه).'),
    ('سفارش‌ها با پست پیشتاز یا تیپاکس، به انتخاب خریدار، ارسال می‌شوند. پس از ارسال، کد رهگیری پیامک می‌شود.',
     'سفارش‌ها با پست پیشتاز یا تیپاکس، به انتخاب خریدار، ارسال می‌شوند و ۴ تا ۶ روز کاری بعد می‌رسند. پس از '
     'ارسال، کد رهگیری پیامک می‌شود.\n\n'
     '## گارانتی\n'
     'شرایط گارانتی در صفحه «گارانتی» آمده است.'),
]


def forwards(apps, schema_editor):
    StoreSettings, Product = apps.get_model('shop', 'StoreSettings'), apps.get_model('shop', 'Product')
    Faq, Page = apps.get_model('shop', 'Faq'), apps.get_model('shop', 'Page')
    for store in StoreSettings.objects.all():
        if store.store_name == 'نام فروشگاه':
            store.store_name = 'ویوو'
        if (store.shipping_post_rial, store.shipping_tipax_rial) == PLACEHOLDER_FEES:
            store.shipping_post_rial = store.shipping_tipax_rial = 0
        elif store.shipping_tipax_rial:
            store.tipax_on_delivery = False  # a Tipax fee the client set in the panel stays the site's
        store.post_days = DAYS.get(store.post_days, store.post_days)
        store.tipax_days = DAYS.get(store.tipax_days, store.tipax_days)
        store.save()
    for product in Product.objects.all():
        if product.price_rial == OLD_PRICE:
            product.price_rial = NEW_PRICE
        specs = []
        for pair in product.specs:
            specs += NEW_CHARGE if pair == OLD_CHARGE else [pair]
        if not any(pair[0] == WARRANTY_SPEC[0] for pair in specs):
            specs.append(WARRANTY_SPEC)
        product.specs = specs
        product.save()
    for question, (old, new) in FAQ.items():
        Faq.objects.filter(question=question, answer=old).update(answer=new)
    Page.objects.filter(slug='warranty', body__contains='[مدت گارانتی').update(body=WARRANTY_PAGE)
    Page.objects.filter(slug='shipping', body__startswith=OLD_SHIPPING_START).update(body=SHIPPING_PAGE)
    for page in Page.objects.filter(slug='terms'):
        for old, new in TERMS:
            page.body = page.body.replace(old, new)
        page.save()
    for page in Page.objects.filter(body__contains='[نام فروشگاه]'):
        page.body = page.body.replace('[نام فروشگاه]', 'ویوو')
        page.save()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0003_wiwu_colors'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='tipax_on_delivery',
            field=models.BooleanField(default=True, verbose_name='هزینه تیپاکس با خریدار، هنگام تحویل (پس‌کرایه)'),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_on_delivery',
            field=models.BooleanField(default=False, verbose_name='هزینه ارسال هنگام تحویل (پس‌کرایه)'),
        ),
        migrations.AlterField(
            model_name='storesettings',
            name='store_name',
            field=models.CharField(default='ویوو', max_length=80, verbose_name='نام فروشگاه'),
        ),
        migrations.AlterField(
            model_name='storesettings',
            name='post_days',
            field=models.CharField(default='۴ تا ۶ روز کاری', max_length=60, verbose_name='زمان رسیدن با پست'),
        ),
        migrations.AlterField(
            model_name='storesettings',
            name='tipax_days',
            field=models.CharField(default='۴ تا ۶ روز کاری', max_length=60, verbose_name='زمان رسیدن با تیپاکس'),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
