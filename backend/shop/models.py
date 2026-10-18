"""
The store's data. Money is always whole rials (bank SMS and Shaparak count in rials); the site shows
tomans. An order copies the price, shipping fee and card it was given, so later changes in the panel
never alter an order that already exists.
"""
import secrets

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

private_storage = FileSystemStorage(location=settings.PRIVATE_ROOT)

CODE_ALPHABET = '23456789ABCDEFGHJKMNPQRSTUVWXYZ'  # no 0/O, 1/I/L: read out over the phone


class StoreSettings(models.Model):
    """One row (pk=1): the store's details, fees and timings, edited in the panel."""

    store_name = models.CharField('نام فروشگاه', max_length=80, default='نام فروشگاه')
    tagline = models.CharField('شعار', max_length=160, blank=True)
    phone = models.CharField('تلفن تماس', max_length=40, blank=True)
    email = models.EmailField('ایمیل', blank=True)
    address = models.CharField('نشانی', max_length=300, blank=True)
    postal_code = models.CharField('کد پستی', max_length=10, blank=True)
    hours = models.CharField('ساعات پاسخگویی', max_length=120, blank=True)
    instagram = models.CharField('اینستاگرام (بدون @)', max_length=60, blank=True)
    owner_mobile = models.CharField('موبایل مدیر (پیامک سفارش‌ها)', max_length=11, blank=True)
    shipping_post_rial = models.PositiveBigIntegerField('هزینه پست پیشتاز (ریال)', default=0)
    shipping_tipax_rial = models.PositiveBigIntegerField('هزینه تیپاکس (ریال)', default=0)
    post_days = models.CharField('زمان رسیدن با پست', max_length=60, default='۲ تا ۴ روز کاری')
    tipax_days = models.CharField('زمان رسیدن با تیپاکس', max_length=60, default='۱ تا ۳ روز کاری')
    payment_minutes = models.PositiveSmallIntegerField('مهلت پرداخت (دقیقه)', default=30)
    reminder_minutes = models.PositiveSmallIntegerField('یادآوری پرداخت پس از (دقیقه)', default=15)
    return_days = models.PositiveSmallIntegerField('مهلت بازگشت کالا (روز کاری)', default=7)
    enamad_html = models.TextField('کد نماد اعتماد (همان‌طور که اینماد می‌دهد)', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = 'تنظیمات فروشگاه'

    def __str__(self):
        return self.store_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def shipping_options(self):
        return [
            {'id': 'post', 'name': 'پست پیشتاز', 'price_rial': self.shipping_post_rial, 'days': self.post_days},
            {'id': 'tipax', 'name': 'تیپاکس', 'price_rial': self.shipping_tipax_rial, 'days': self.tipax_days},
        ]

    def shipping_fee(self, method):
        return {o['id']: o['price_rial'] for o in self.shipping_options()}[method]


class Product(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField('نام', max_length=120)
    subtitle = models.CharField('توضیح کوتاه', max_length=200, blank=True)
    description = models.TextField('توضیحات', blank=True)
    price_rial = models.PositiveBigIntegerField('قیمت (ریال)')
    is_available = models.BooleanField('موجود', default=True)
    specs = models.JSONField('مشخصات', default=list, blank=True, help_text='[["عنوان", "مقدار"], …]')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'کالا'
        verbose_name_plural = 'کالاها'

    def __str__(self):
        return self.name

    def shown_colors(self):
        return [color for color in self.colors.all() if color.shown]


class Color(models.Model):
    """A colour the product comes in, all at the product's price. While only one colour is on show (black,
    at launch) the site doesn't ask; with more, the buyer picks one on the page and at checkout."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='colors')
    name = models.CharField('نام رنگ', max_length=40)
    swatch = models.CharField('کد رنگ', max_length=7, default='#17181b', help_text='مثل #17181b، برای دایره‌ی رنگ در سایت')
    shown = models.BooleanField('نمایش در سایت', default=True)
    available = models.BooleanField('موجود', default=True)
    photo = models.CharField('عکس', max_length=120, blank=True,
                             help_text='عکس کیف در این رنگ، از پوشه‌ی تصاویر سایت، مثل images/colors/brown.webp')
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'رنگ'
        verbose_name_plural = 'رنگ‌ها'
        ordering = ['position', 'id']

    def __str__(self):
        return self.name


class Card(models.Model):
    """A destination card for card-to-card payments. All in the owner's name (see PLAN.md)."""

    bank = models.CharField('بانک', max_length=40)
    number = models.CharField('شماره کارت', max_length=16)
    holder = models.CharField('نام صاحب کارت', max_length=80)
    active = models.BooleanField('فعال', default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'کارت'
        verbose_name_plural = 'کارت‌ها'
        ordering = ['position', 'id']

    def __str__(self):
        return f'{self.bank} …{self.number[-4:]}'


def new_order_code():
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def new_order_token():
    return secrets.token_urlsafe(12)


class Order(models.Model):
    class Status(models.TextChoices):
        AWAITING = 'awaiting_payment', 'در انتظار پرداخت'
        REVIEW = 'needs_review', 'بررسی پرداخت'
        PAID = 'paid', 'پرداخت‌شده'
        PREPARING = 'preparing', 'در حال آماده‌سازی'
        SHIPPED = 'shipped', 'ارسال‌شده'
        DELIVERED = 'delivered', 'تحویل‌شده'
        EXPIRED = 'expired', 'منقضی‌شده'
        CANCELLED = 'cancelled', 'لغوشده'

    class Shipping(models.TextChoices):
        POST = 'post', 'پست پیشتاز'
        TIPAX = 'tipax', 'تیپاکس'

    code = models.CharField('کد سفارش', max_length=8, unique=True, default=new_order_code)
    token = models.CharField(max_length=24, unique=True, default=new_order_token)  # the buyer's link
    status = models.CharField('وضعیت', max_length=20, choices=Status.choices, default=Status.AWAITING, db_index=True)

    phone = models.CharField('موبایل', max_length=11, db_index=True)
    name = models.CharField('نام گیرنده', max_length=80)
    province = models.CharField('استان', max_length=40)
    city = models.CharField('شهر', max_length=60)
    address = models.TextField('نشانی')
    postal_code = models.CharField('کد پستی', max_length=10)
    shipping = models.CharField('روش ارسال', max_length=10, choices=Shipping.choices)
    is_gift = models.BooleanField('هدیه (بدون قیمت در بسته)', default=False)

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='orders')
    product_name = models.CharField(max_length=120)
    color = models.ForeignKey(Color, null=True, blank=True, on_delete=models.SET_NULL, related_name='orders')
    color_name = models.CharField('رنگ', max_length=40, blank=True)  # as it was when ordered
    unit_price_rial = models.PositiveBigIntegerField()
    shipping_rial = models.PositiveBigIntegerField()
    offset_rial = models.PositiveBigIntegerField()  # makes the amount unique, see orders.choose_amount
    amount_rial = models.PositiveBigIntegerField('مبلغ پرداخت (ریال)', db_index=True)

    card = models.ForeignKey(Card, null=True, blank=True, on_delete=models.SET_NULL, related_name='orders')
    card_bank = models.CharField(max_length=40)
    card_number = models.CharField(max_length=16)
    card_holder = models.CharField(max_length=80)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField()
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_via = models.CharField(max_length=10, blank=True)  # 'auto' (cartbecart) or 'manual' (staff)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    provider_ref = models.CharField(max_length=80, blank=True)

    # "I've paid": what the buyer tells us when the automatic match didn't happen.
    claim_reference = models.CharField('شماره پیگیری واریز', max_length=40, blank=True)
    claim_card_last4 = models.CharField('۴ رقم آخر کارت مبدأ', max_length=4, blank=True)
    claim_time = models.CharField('زمان واریز', max_length=40, blank=True)
    claim_note = models.CharField('توضیح خریدار', max_length=300, blank=True)
    claim_file = models.FileField(storage=private_storage, upload_to='claims/%Y/%m/', blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)

    tracking_code = models.CharField('کد رهگیری مرسوله', max_length=40, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    staff_note = models.TextField('یادداشت داخلی', blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'سفارش'
        verbose_name_plural = 'سفارش‌ها'
        ordering = ['-created_at']
        permissions = [
            ('approve_payment', 'تأیید یا رد پرداخت'),
        ]

    def __str__(self):
        return f'{self.code} — {self.name}'


class ReturnRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = 'requested', 'درخواست‌شده'
        RECEIVED = 'received', 'کالا رسید'
        REFUNDED = 'refunded', 'مبلغ برگشت داده شد'
        REJECTED = 'rejected', 'ردشده'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='returns')
    status = models.CharField('وضعیت', max_length=12, choices=Status.choices, default=Status.REQUESTED)
    reason = models.TextField('دلیل')
    sheba = models.CharField('شبا', max_length=26)
    account_holder = models.CharField('نام صاحب حساب', max_length=80)
    refund_reference = models.CharField('شماره پیگیری بازپرداخت', max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    staff_note = models.TextField('یادداشت داخلی', blank=True)

    class Meta:
        verbose_name = 'درخواست بازگشت'
        verbose_name_plural = 'درخواست‌های بازگشت'
        ordering = ['-created_at']
        permissions = [
            ('refund', 'ثبت بازپرداخت'),
        ]


class PaymentEvent(models.Model):
    """Everything the payment provider tells us, kept as received, plus what we did with it."""

    source = models.CharField(max_length=20)
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name='payment_events')
    amount_rial = models.PositiveBigIntegerField(null=True, blank=True)
    provider_ref = models.CharField(max_length=80, blank=True, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    outcome = models.CharField(max_length=20)  # matched, late, second, repeat, unmatched, unparsed
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class OtpCode(models.Model):
    phone = models.CharField(max_length=11, db_index=True)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)


class SmsLog(models.Model):
    phone = models.CharField(max_length=11)
    kind = models.CharField(max_length=30)
    text = models.TextField()
    status = models.CharField(max_length=10)  # sent, failed, console
    error = models.CharField(max_length=300, blank=True)
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name='sms')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=40)
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit')
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Page(models.Model):
    """About, terms, returns, privacy, shipping, warranty: plain text with light markup (see text.py)."""

    slug = models.SlugField(unique=True)
    title = models.CharField('عنوان', max_length=120)
    body = models.TextField('متن')
    position = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'صفحه'
        verbose_name_plural = 'صفحه‌ها'
        ordering = ['position', 'id']

    def __str__(self):
        return self.title


class Faq(models.Model):
    question = models.CharField('پرسش', max_length=200)
    answer = models.TextField('پاسخ')
    position = models.PositiveSmallIntegerField(default=0)
    published = models.BooleanField('نمایش', default=True)

    class Meta:
        verbose_name = 'پرسش متداول'
        verbose_name_plural = 'پرسش‌های متداول'
        ordering = ['position', 'id']

    def __str__(self):
        return self.question
