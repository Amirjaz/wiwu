"""
Transactional SMS. Every message is logged (SmsLog) and shown in the panel.

Backends (settings.SMS_BACKEND):
- 'console': development; prints the text and logs it, sends nothing.
- 'kavenegar': Kavenegar's verify/lookup API. Each kind below is a template created in the Kavenegar
  panel (name: SMS_TEMPLATE_<KIND> in .env, default 'ps-<kind>'), whose placeholders %token, %token2,
  %token3 (no spaces allowed) and %token10 (spaces allowed) get the values listed for that kind.
  Template messages aren't blocked as advertising and arrive fast. The texts here are what we log
  and the wording to use when creating the templates.
"""
import json
import logging
import os
import urllib.parse
import urllib.request

from django.conf import settings

from .models import SmsLog, StoreSettings

log =logging.getLogger(__name__)

# kind: (text, tokens in order: token, token2, token3, then token10)
MESSAGES = {
    'otp': ('کد تأیید {store}: {code}', ['code']),
    'order_created': (
        'سفارش {code} ثبت شد. مبلغ {amount} تومان را تا {minutes} دقیقه کارت‌به‌کارت کنید: {link}',
        ['code', 'amount', 'link', 'minutes'],
    ),
    'reminder': ('سفارش {code} هنوز پرداخت نشده. ادامه پرداخت: {link}', ['code', 'link']),
    'paid': ('پرداخت سفارش {code} تأیید شد. پیگیری: {link}', ['code', 'link']),
    'payment_not_found': (
        'واریز سفارش {code} پیدا نشد. اگر پرداخت کرده‌اید با ما تماس بگیرید: {link}',
        ['code', 'link'],
    ),
    'shipped': ('سفارش {code} با {carrier} ارسال شد. کد رهگیری: {tracking}', ['code', 'tracking', 'link', 'carrier']),
    'return_received': ('کالای سفارش {code} به دست ما رسید. بازپرداخت به‌زودی انجام می‌شود.', ['code']),
    'refunded': ('مبلغ سفارش {code} به حساب شما برگشت داده شد. شماره پیگیری: {reference}', ['code', 'reference']),
    'owner_new_order': ('سفارش تازه {code}، {amount} تومان، پرداخت‌شده.', ['code', 'amount']),
    'owner_review': ('پرداخت سفارش {code} نیاز به بررسی دارد.', ['code']),
    'owner_forwarder': (
        'پرداخت‌ها خودکار تأیید نمی‌شوند ({count} سفارش بی‌پاسخ). گوشی پیامک‌های بانک روشن و متصل است؟',
        ['count'],
    ),
}


def template_name(kind):
    return os.getenv(f'SMS_TEMPLATE_{kind.upper()}', f'ps-{kind.replace("_", "-")}')


def render(kind, values):
    """The message text. Numbers for reading (amounts, minutes, counts) arrive already in Persian
    digits; codes, links and tracking numbers stay Latin so they can be copied and tapped."""
    text, _ = MESSAGES[kind]
    return text.format(store=StoreSettings.load().store_name, **values)


def send(kind, phone, order=None, **values):
    """Send one message; never raises (a failed SMS must not break an order). Returns True if sent."""
    text = render(kind, values)
    entry = SmsLog(phone=phone, kind=kind, text=text, order=order)
    try:
        if settings.SMS_BACKEND == 'console':
            print(f'[SMS → {phone}] {text}', flush=True)
            entry.status = 'console'
        elif settings.SMS_BACKEND == 'kavenegar':
            _kavenegar(phone, kind, values)
            entry.status = 'sent'
        else:
            raise RuntimeError(f'unknown SMS_BACKEND {settings.SMS_BACKEND!r}')
    except Exception as exc:  # noqa: BLE001 — logged and shown in the panel
        log.warning('SMS %s to %s failed: %s', kind, phone, exc)
        entry.status, entry.error = 'failed', str(exc)[:300]
    entry.save()
    return entry.status != 'failed'


def _kavenegar(phone, kind, values):
    if not settings.KAVENEGAR_API_KEY:
        raise RuntimeError('KAVENEGAR_API_KEY is not set')
    _, tokens = MESSAGES[kind]
    names = ['token', 'token2', 'token3']
    params = {'receptor': phone, 'template': template_name(kind)}
    for i, key in enumerate(tokens):
        value = str(values[key])
        if i < 3:
            params[names[i]] = value.replace(' ', '‌')  # no spaces allowed in these
        else:
            params['token10'] = value
    url = f'https://api.kavenegar.com/v1/{settings.KAVENEGAR_API_KEY}/verify/lookup.json?{urllib.parse.urlencode(params)}'
    with urllib.request.urlopen(url, timeout=10) as response:
        body = json.loads(response.read().decode())
    status = body.get('return', {}).get('status')
    if status != 200:
        raise RuntimeError(f'kavenegar {status}: {body.get("return", {}).get("message")}')
