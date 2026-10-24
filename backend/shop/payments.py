"""
Automatic confirmation through cartbecart.com (PAYMENT_PROVIDER=cartbecart). Their app on the shop's
forwarder phone reads the bank's deposit SMS; they match each deposit to an order by its exact amount
and tell us. Their docs: dashboard → مستندات API (base https://api.cartbecart.com, header X-API-Key,
the Pro or Max plan). Amounts are rials everywhere.

1. Checkout (orders.place → create_order): we register the order (price + shipping, our order code as
   merchant_order_id). They add 1–999 rials to make the amount unique and choose the card (the one
   marked default in their dashboard); the card's number and holder come from their public pay
   endpoint. Our own order page shows card, amount and countdown, as with manual payments.
2. The result: a signed POST to /api/payments/cartbecart/ for each change (order.paid,
   order.needs_review, order.expired, order.cancelled), HMAC-SHA256 over "timestamp.body" with the key
   from their dashboard (Settings → Webhook) in CARTBECART_WEBHOOK_SECRET. Sent at least once, so
   repeats are recognised by event_id (orders.cartbecart_event).
3. A backup for a missed webhook: the minute timer asks for the status of orders whose result could
   still change (orders.sync_cartbecart).

This module only talks to their API; orders.py decides what happens to an order.
"""
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .persian import latin_digits

log = logging.getLogger(__name__)

TIMEOUT = 10  # seconds per call; checkout waits for two
SIGNATURE_MAX_AGE = 300  # seconds: older signed requests are refused, so a recorded one can't be replayed
EVENTS = {'order.paid': 'paid', 'order.needs_review': 'needs_review', 'order.expired': 'expired',
          'order.cancelled': 'cancelled'}


class CartbecartError(Exception):
    """A refused or failed call. status is the HTTP status (None if they couldn't be reached);
    detail is their reason, in Persian, for logs and the owner."""

    def __init__(self, status, detail):
        super().__init__(f'cartbecart {status}: {detail}' if status else f'cartbecart: {detail}')
        self.status, self.detail = status, detail


def enabled():
    return settings.PAYMENT_PROVIDER == 'cartbecart'


def _call(method, path, body=None, with_key=True):
    headers = {'Accept': 'application/json', 'User-Agent': 'purseshop/1'}
    if with_key:
        if not settings.CARTBECART_API_KEY:
            raise CartbecartError(None, 'CARTBECART_API_KEY is not set')
        headers['X-API-Key'] = settings.CARTBECART_API_KEY
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(settings.CARTBECART_API_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode() or 'null')
    except urllib.error.HTTPError as exc:
        # Every refusal is {"detail": "..."} (a list of field problems for a malformed request).
        try:
            detail = json.loads(exc.read().decode()).get('detail')
        except Exception:  # noqa: BLE001 — not their JSON, e.g. a proxy's error page
            detail = None
        if detail is not None and not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False)
        raise CartbecartError(exc.code, (detail or exc.reason or '')[:300]) from None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise CartbecartError(None, str(getattr(exc, 'reason', exc))[:300]) from None


def _token_path(token):
    return urllib.parse.quote(token, safe='')


def create_order(code, amount_rial, callback_url, name='', phone=''):
    """Registers one of our orders. Returns token, ref (their CBC- code), amount_rial (the unique amount
    to pay), expires_at, card_number, card_holder and payment_url. Raises CartbecartError."""
    body = {'amount': amount_rial, 'callback_url': callback_url, 'merchant_order_id': code}
    # Optional, but an empty one is refused (their phone check wants 09…): send them only with a value.
    if name:
        body['customer_name'] = name[:80]
    if phone:
        body['customer_phone'] = phone
    created = _call('POST', '/api/v1/public/orders', body)
    if not isinstance(created, dict):
        raise CartbecartError(None, f'unexpected answer: {str(created)[:200]}')
    token = str(created.get('payment_token') or '')
    unique = created.get('unique_amount') if token else None
    if not isinstance(unique, int) or not amount_rial <= unique < amount_rial + 1000:
        raise CartbecartError(None, f'unexpected answer: {str(created)[:200]}')
    # Card and holder aren't in that answer: their public pay endpoint (no key) has them.
    page = _call('GET', f'/api/v1/pay/{_token_path(token)}', with_key=False) or {}
    number = ''.join(c for c in latin_digits(page.get('card_number') or '') if c.isdigit())
    if len(number) != 16:
        raise CartbecartError(None, f'no card in the pay page: {str(page)[:200]}')
    expires = parse_datetime(str(created.get('expires_at') or page.get('expires_at') or ''))
    return {
        'token': token,
        'ref': str(created.get('order_code') or '')[:80],
        'amount_rial': unique,
        'expires_at': expires or timezone.now() + timedelta(minutes=30),
        'card_number': number,
        'card_holder': str(page.get('card_owner') or '')[:80],
        'payment_url': str(created.get('payment_url') or ''),
    }


def order_status(token):
    """Their current view of one order: {'status': pending|paid|needs_review|expired, 'grace_ends_at', …}."""
    return _call('GET', f'/api/v1/public/orders/{_token_path(token)}') or {}


def shop_config():
    """The shop's settings on their side (grace_minutes, …); checks the key and plan."""
    return _call('GET', '/api/v1/public/shop-config') or {}


def signature_ok(body, timestamp, signature):
    """X-CBC-Signature is "sha256=" + hex HMAC-SHA256 of "<X-CBC-Timestamp>.<raw body>"."""
    secret = settings.CARTBECART_WEBHOOK_SECRET
    if not secret or not timestamp or not signature:
        return False
    try:
        age = abs(time.time() - int(timestamp))
    except ValueError:
        return False
    if age > SIGNATURE_MAX_AGE:
        return False
    expected = 'sha256=' + hmac.new(secret.encode(), timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def parse_event(body):
    """A webhook body → its parts, or None if it isn't their JSON."""
    try:
        event = json.loads(body or b'')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(event, dict):
        return None
    order = event.get('order') if isinstance(event.get('order'), dict) else {}
    amount = order.get('unique_amount')
    return {
        'payload': event,
        'event_id': str(event.get('event_id') or '')[:80],
        'status': EVENTS.get(event.get('event')),  # None for an event we don't know
        'reason': str(event.get('reason') or ''),
        'code': str(order.get('merchant_order_id') or ''),
        'ref': str(order.get('order_code') or ''),
        'amount_rial': amount if isinstance(amount, int) else None,
    }
