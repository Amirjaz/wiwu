"""
Automatic confirmation through cartbecart.com. It reads the bank's deposit SMS on the shop's
forwarder phone and tells us about each deposit; we match it to an order by its exact amount
(orders.deposit). Without it (PAYMENT_PROVIDER=manual) everything still works: buyers press
"I've paid" and staff confirm in the panel.

STILL TO DO WITH THEIR DOCS (behind their login; the client's Max account gives us access):
- parse(): the webhook's real field names, and whether amounts are rials or tomans
  (CARTBECART_AMOUNT_UNIT, default rial: bank SMS count in rials).
- verify(): ask their API whether the deposit is real before trusting a webhook. Until then the
  webhook URL carries a secret (CARTBECART_WEBHOOK_SECRET) that only cartbecart knows.
- Whether they need each order registered with them first (card + amount), and how they rotate
  between the 5 cards. Today we pick the card (least recently used) and the amount ourselves.
Every payload is stored as received (PaymentEvent), so nothing is lost while this is being
finished, and payloads we can't read show in the panel.
"""
import hmac
import json
import logging
import os

from django.conf import settings

from . import orders
from .models import PaymentEvent
from .persian import latin_digits

log = logging.getLogger(__name__)

AMOUNT_KEYS = ('amount', 'amount_rial', 'price')  # TODO(cartbecart docs)
REF_KEYS = ('id', 'transaction_id', 'reference', 'ref')  # TODO(cartbecart docs)


def secret_ok(secret):
    expected = settings.CARTBECART_WEBHOOK_SECRET
    return bool(expected) and hmac.compare_digest(secret.encode(), expected.encode())


def parse(payload):
    """(amount in rials, provider reference) or (None, '') if the payload can't be read."""
    data = payload.get('data') if isinstance(payload.get('data'), dict) else payload
    amount = next((data[k] for k in AMOUNT_KEYS if k in data), None)
    ref = next((str(data[k]) for k in REF_KEYS if k in data), '')
    try:
        amount = int(float(latin_digits(amount).replace(',', '').replace('٬', '')))
    except (TypeError, ValueError):
        return None, ref
    if os.getenv('CARTBECART_AMOUNT_UNIT', 'rial') == 'toman':
        amount *= 10
    return amount, ref[:80]


def verify(amount_rial, ref):
    """TODO(cartbecart docs): confirm the deposit through their API. True until we can."""
    return True


def webhook(body):
    """Handle one webhook call; returns the PaymentEvent."""
    try:
        payload = json.loads(body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {'raw': (body or b'')[:2000].decode('utf-8', 'replace')}
    if not isinstance(payload, dict):
        payload = {'raw': payload}
    amount, ref = parse(payload)
    if amount is None or amount <= 0:
        log.warning('cartbecart payload without an amount: %s', str(payload)[:500])
        return PaymentEvent.objects.create(source='cartbecart', payload=payload, provider_ref=ref, outcome='unparsed')
    if not verify(amount, ref):
        return PaymentEvent.objects.create(source='cartbecart', amount_rial=amount, payload=payload,
                                           provider_ref=ref, outcome='unverified')
    return orders.deposit(amount, 'cartbecart', payload, ref)
