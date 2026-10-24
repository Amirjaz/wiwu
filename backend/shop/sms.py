"""
Transactional SMS. Every message is logged (SmsLog) and shown in the panel.

Backends (settings.SMS_BACKEND):
- 'console': development; prints the text and logs it, sends nothing.
- 'kavenegar': Kavenegar's REST API (https://kavenegar.com/rest.html), each kind one of two ways:
  - plain text (sms/send) from the line KAVENEGAR_SENDER (empty: the account's default line). Works as
    soon as the account has credit; the text is the one below.
  - a template (verify/lookup), for the kinds listed in KAVENEGAR_TEMPLATES ('all' for every kind).
    Each is created in the Kavenegar panel and approved by Kavenegar first (name: SMS_TEMPLATE_<KIND>
    in .env, default 'ps-<kind>'); its placeholders %token, %token2, %token3 (no spaces allowed) and
    %token10 (spaces allowed) get the values listed for that kind. Template messages aren't blocked as
    advertising and arrive fast; the service needs Kavenegar's Advanced plan.
  The texts here are what plain messages say, what we log, and the wording to use for the templates.
"""
import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

from .models import SmsLog, StoreSettings

log = logging.getLogger(__name__)

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


def uses_template(kind):
    """Whether Kavenegar sends this kind from an approved template rather than as plain text."""
    return 'all' in settings.KAVENEGAR_TEMPLATES or kind in settings.KAVENEGAR_TEMPLATES


def printable(text):
    """A Windows terminal that isn't UTF-8 can't print Persian: escape it rather than fail."""
    encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
    return text.encode(encoding, 'backslashreplace').decode(encoding)


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
            print(printable(f'[SMS → {phone}] {text}'), flush=True)
            entry.status = 'console'
        elif settings.SMS_BACKEND == 'kavenegar':
            if uses_template(kind):
                _lookup(phone, kind, values)
            else:
                params = {'receptor': phone, 'message': text}
                if settings.KAVENEGAR_SENDER:
                    params['sender'] = settings.KAVENEGAR_SENDER
                kavenegar('sms/send', **params)
            entry.status = 'sent'
        else:
            raise RuntimeError(f'unknown SMS_BACKEND {settings.SMS_BACKEND!r}')
    except Exception as exc:  # noqa: BLE001 — logged and shown in the panel
        log.warning('SMS %s to %s failed: %s', kind, phone, exc)
        entry.status, entry.error = 'failed', str(exc)[:300]
    entry.save()
    return entry.status != 'failed'


def _lookup(phone, kind, values):
    _, tokens = MESSAGES[kind]
    names = ['token', 'token2', 'token3']
    params = {'receptor': phone, 'template': template_name(kind)}
    for i, key in enumerate(tokens):
        value = str(values[key])
        if i < 3:
            params[names[i]] = value.replace(' ', '‌')  # no spaces allowed in these: a zero-width non-joiner
        else:
            params['token10'] = value
    kavenegar('verify/lookup', **params)


def kavenegar(method, **params):
    """Calls one Kavenegar API method (e.g. 'sms/send', 'account/info') and returns its entries.
    Raises with Kavenegar's own reason (in Persian) when it refuses."""
    if not settings.KAVENEGAR_API_KEY:
        raise RuntimeError('KAVENEGAR_API_KEY is not set')
    url = f'https://api.kavenegar.com/v1/{settings.KAVENEGAR_API_KEY}/{method}.json'
    # POST, as their SDKs do: no length limit, and the message stays out of URLs and server logs.
    request = urllib.request.Request(url, data=urllib.parse.urlencode(params).encode())
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        # A refusal comes with the same HTTP status and a JSON body that says why (no credit, bad key…).
        try:
            body = json.loads(exc.read().decode())
        except Exception:  # noqa: BLE001 — not Kavenegar's JSON, e.g. a proxy's error page
            raise RuntimeError(f'kavenegar HTTP {exc.code}') from None
    result = body.get('return') or {}
    if result.get('status') != 200:
        raise RuntimeError(f'kavenegar {result.get("status")}: {result.get("message")}')
    return body.get('entries')
