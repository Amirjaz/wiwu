"""
What happens to an order, in one place. Views and the panel call these; nothing else changes an
order's status.

    awaiting_payment ──(amount matched)──────────────► paid ─► preparing ─► shipped ─► delivered
          │      └──(buyer: "I've paid")──► needs_review ─(staff approve)─┘    │
          │                                       └─(staff reject)─► cancelled  │
          └──(window over)──► expired ──(late money / claim)──► needs_review    └─► return request
"""
import hashlib
import hmac
import logging
import random
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import sms
from .models import AuditLog, Card, Color, Order, OtpCode, PaymentEvent, ReturnRequest, StoreSettings
from .persian import fa_digits, toman

log = logging.getLogger(__name__)

OPEN = (Order.Status.AWAITING, Order.Status.REVIEW)
LATE_MATCH_HOURS = 48  # money for an expired order still finds it this long after it was placed
OFFSET_MAX_TOMAN = 999

OTP_TTL = timedelta(minutes=5)
OTP_GAP = timedelta(seconds=60)  # between two codes to the same phone
OTP_PER_HOUR = 5  # codes per phone per hour
OTP_IP_PER_HOUR = 15  # codes per address per hour (stops SMS-pumping from one place)
OTP_MAX_TRIES = 5


class OrderError(Exception):
    """A buyer-facing refusal: .code is what the frontend shows (see the islands' messages)."""

    def __init__(self, code, **extra):
        super().__init__(code)
        self.code, self.extra = code, extra


def link(order):
    return f'{settings.PUBLIC_URL}/o/{order.token}/'


def audit(action, order=None, user=None, detail=''):
    AuditLog.objects.create(action=action, order=order, user=user if user and user.is_authenticated else None, detail=detail)


# ── One-time codes ──────────────────────────────────────────────────────────────────────────────

def _hash(phone, code):
    return hmac.new(settings.SECRET_KEY.encode(), f'{phone}:{code}'.encode(), hashlib.sha256).hexdigest()


def send_otp(phone, ip):
    """Text a 5-digit code to phone; returns (seconds until another may be asked for, the code)."""
    now = timezone.now()
    recent = OtpCode.objects.filter(phone=phone, created_at__gte=now - timedelta(hours=1))
    last = recent.order_by('-created_at').first()
    if last and now - last.created_at < OTP_GAP:
        raise OrderError('otp_wait', wait=int((OTP_GAP - (now - last.created_at)).total_seconds()) + 1)
    if recent.count() >= OTP_PER_HOUR:
        raise OrderError('otp_limit')
    if ip and OtpCode.objects.filter(ip=ip, created_at__gte=now - timedelta(hours=1)).count() >= OTP_IP_PER_HOUR:
        raise OrderError('otp_limit')
    code = f'{secrets.randbelow(90000) + 10000}'
    OtpCode.objects.create(phone=phone, code_hash=_hash(phone, code), ip=ip)
    if not sms.send('otp', phone, code=code):
        raise OrderError('sms_failed')
    return int(OTP_GAP.total_seconds()), code


def check_otp(phone, code):
    """Uses up the phone's latest live code if it matches; raises otherwise."""
    otp = (OtpCode.objects.filter(phone=phone, used_at=None, created_at__gte=timezone.now() - OTP_TTL)
           .order_by('-created_at').first())
    if not otp:
        raise OrderError('otp_expired')
    if otp.attempts >= OTP_MAX_TRIES:
        raise OrderError('otp_tries')
    if not hmac.compare_digest(otp.code_hash, _hash(phone, str(code).strip())):
        OtpCode.objects.filter(pk=otp.pk).update(attempts=otp.attempts + 1)
        raise OrderError('otp_wrong')
    OtpCode.objects.filter(pk=otp.pk).update(used_at=timezone.now())


# ── Placing an order ────────────────────────────────────────────────────────────────────────────

def _amounts_in_use():
    """Amounts a payment could still arrive for: open orders, and recently expired ones."""
    since = timezone.now() - timedelta(hours=LATE_MATCH_HOURS)
    return set(
        Order.objects.filter(status__in=OPEN).values_list('amount_rial', flat=True)
    ) | set(
        Order.objects.filter(status=Order.Status.EXPIRED, created_at__gte=since).values_list('amount_rial', flat=True)
    )


def choose_amount(base_rial):
    """base + a random 1…999 toman no open order has, so a bank deposit points at exactly one order.
    The buyer pays the extra (decided 2026-10-14)."""
    taken = _amounts_in_use()
    free = [t * 10 for t in range(1, OFFSET_MAX_TOMAN + 1) if base_rial + t * 10 not in taken]
    if not free:
        raise OrderError('busy')
    offset = random.choice(free)
    return offset, base_rial + offset


def _next_card():
    card = Card.objects.filter(active=True).order_by('last_used_at', 'position', 'id').first()
    if not card:
        raise OrderError('no_card')
    card.last_used_at = timezone.now()
    card.save(update_fields=['last_used_at'])
    return card


def pick_color(product, color_id):
    """The colour for a new order: the one the buyer picked, or the only one on show. None for a product
    with no colours. Checked before the SMS code is used, so a bad pick doesn't cost the buyer a code."""
    shown = product.shown_colors()
    if not shown:
        return None
    if len(shown) == 1 and not color_id:
        color = shown[0]
    else:
        color = next((c for c in shown if str(c.pk) == str(color_id)), None)
        if color is None:
            raise OrderError('color')
    if not color.available:
        raise OrderError('color_unavailable')
    return color


def place(product, data, ip=None, color=None):
    """data is already cleaned (views.checkout); color from pick_color. Returns the new order."""
    store = StoreSettings.load()
    if not product.is_available:
        raise OrderError('unavailable')
    if color is None and product.shown_colors():
        color = pick_color(product, None)
    shipping_rial = store.shipping_fee(data['shipping'])
    for _ in range(5):
        try:
            # IMMEDIATE transactions (settings) serialise writers, so two buyers can't get one amount.
            with transaction.atomic():
                offset, amount = choose_amount(product.price_rial + shipping_rial)
                card = _next_card()
                order = Order.objects.create(
                    phone=data['phone'], name=data['name'], province=data['province'], city=data['city'],
                    address=data['address'], postal_code=data['postal_code'], shipping=data['shipping'],
                    is_gift=data['is_gift'], product=product, product_name=product.name,
                    color=color, color_name=color.name if color else '',
                    unit_price_rial=product.price_rial, shipping_rial=shipping_rial, offset_rial=offset,
                    amount_rial=amount, card=card, card_bank=card.bank, card_number=card.number,
                    card_holder=card.holder, expires_at=timezone.now() + timedelta(minutes=store.payment_minutes),
                    ip=ip,
                )
            break
        except IntegrityError:  # code or token collision: try new ones
            continue
    else:
        raise OrderError('busy')
    audit('placed', order, detail=f'{toman(amount)} تومان، کارت …{card.number[-4:]}')
    sms.send('order_created', order.phone, order, code=order.code, amount=toman(order.amount_rial),
             link=link(order), minutes=fa_digits(store.payment_minutes))
    return order


# ── Payment ─────────────────────────────────────────────────────────────────────────────────────

def refresh(order):
    """Expire the order if its window is over (the minute timer does this too; pages can't wait)."""
    if order.status == Order.Status.AWAITING and timezone.now() >= order.expires_at:
        updated = Order.objects.filter(pk=order.pk, status=Order.Status.AWAITING).update(status=Order.Status.EXPIRED)
        if updated:
            order.status = Order.Status.EXPIRED
            audit('expired', order)
    return order


def mark_paid(order, via, user=None, detail=''):
    with transaction.atomic():
        updated = Order.objects.filter(pk=order.pk, status__in=OPEN + (Order.Status.EXPIRED,)).update(
            status=Order.Status.PAID, paid_at=timezone.now(), paid_via=via,
            confirmed_by=user if user and user.is_authenticated else None,
        )
    if not updated:
        return False
    order.refresh_from_db()
    audit('paid', order, user, detail or ('تأیید خودکار' if via == 'auto' else 'تأیید دستی'))
    sms.send('paid', order.phone, order, code=order.code, link=link(order))
    owner = StoreSettings.load().owner_mobile
    if owner:
        sms.send('owner_new_order', owner, order, code=order.code, amount=toman(order.amount_rial))
    return True


def to_review(order, why, user=None):
    updated = Order.objects.filter(pk=order.pk, status__in=(Order.Status.AWAITING, Order.Status.EXPIRED)).update(
        status=Order.Status.REVIEW)
    order.refresh_from_db()
    audit('needs_review', order, user, why)
    if updated:
        owner = StoreSettings.load().owner_mobile
        if owner:
            sms.send('owner_review', owner, order, code=order.code)
    return bool(updated)


def reject_payment(order, user, reason=''):
    updated = Order.objects.filter(pk=order.pk, status=Order.Status.REVIEW).update(status=Order.Status.CANCELLED)
    if updated:
        order.refresh_from_db()
        audit('payment_rejected', order, user, reason)
        sms.send('payment_not_found', order.phone, order, code=order.code, link=link(order))
    return bool(updated)


def deposit(amount_rial, source, payload, provider_ref=''):
    """A deposit the provider saw (bank SMS). Finds the one order with that amount:
    awaiting or in review → paid; expired → needs review (late money); already paid → logged as a
    second deposit; no order → logged unmatched (the panel lists those)."""
    since = timezone.now() - timedelta(hours=LATE_MATCH_HOURS)
    order = (Order.objects.filter(amount_rial=amount_rial, created_at__gte=since)
             .exclude(status=Order.Status.CANCELLED).order_by('-created_at').first())
    event = PaymentEvent(source=source, amount_rial=amount_rial, payload=payload, order=order, provider_ref=provider_ref)
    if provider_ref and PaymentEvent.objects.filter(source=source, provider_ref=provider_ref).exists():
        event.outcome = 'repeat'  # the provider told us about this deposit before
    elif order is None:
        event.outcome = 'unmatched'
    else:
        refresh(order)
        if order.status in OPEN:
            Order.objects.filter(pk=order.pk).update(provider_ref=provider_ref)
            mark_paid(order, 'auto')
            event.outcome = 'matched'
        elif order.status == Order.Status.EXPIRED:
            to_review(order, 'واریز پس از پایان مهلت پرداخت رسید')
            event.outcome = 'late'
        else:
            audit('second_deposit', order, detail=f'{toman(amount_rial)} تومان دوباره واریز شد')
            event.outcome = 'second'
    event.save()
    return event


def claim(order, data, upload=None):
    """The buyer says they paid. Allowed while awaiting, and for a while after the window."""
    refresh(order)
    late_limit = order.created_at + timedelta(hours=LATE_MATCH_HOURS)
    if order.status not in (Order.Status.AWAITING, Order.Status.EXPIRED) or timezone.now() > late_limit:
        raise OrderError('claim_closed')
    if cache.get(f'claim:{order.pk}'):
        raise OrderError('claim_wait')
    cache.set(f'claim:{order.pk}', 1, 60)
    order.claim_reference = data['reference']
    order.claim_card_last4 = data['last4']
    order.claim_time = data['time']
    order.claim_note = data['note']
    if upload:
        order.claim_file = upload
    order.claimed_at = timezone.now()
    order.save(update_fields=['claim_reference', 'claim_card_last4', 'claim_time', 'claim_note', 'claim_file', 'claimed_at'])
    to_review(order, f'خریدار: پرداخت کرده‌ام (پیگیری {order.claim_reference or "—"})')


# ── Fulfilment ──────────────────────────────────────────────────────────────────────────────────

def set_preparing(order, user):
    if Order.objects.filter(pk=order.pk, status=Order.Status.PAID).update(status=Order.Status.PREPARING):
        audit('preparing', order, user)
        return True
    return False


def ship(order, user, tracking):
    updated = Order.objects.filter(pk=order.pk, status__in=(Order.Status.PAID, Order.Status.PREPARING)).update(
        status=Order.Status.SHIPPED, tracking_code=tracking, shipped_at=timezone.now())
    if updated:
        order.refresh_from_db()
        audit('shipped', order, user, tracking)
        sms.send('shipped', order.phone, order, code=order.code, tracking=tracking, link=link(order),
                 carrier=order.get_shipping_display())
    return bool(updated)


def deliver(order, user):
    if Order.objects.filter(pk=order.pk, status=Order.Status.SHIPPED).update(
            status=Order.Status.DELIVERED, delivered_at=timezone.now()):
        audit('delivered', order, user)
        return True
    return False


def cancel(order, user, reason=''):
    if Order.objects.filter(pk=order.pk, status__in=OPEN + (Order.Status.EXPIRED, Order.Status.PAID,
                                                              Order.Status.PREPARING)).update(status=Order.Status.CANCELLED):
        audit('cancelled', order, user, reason)
        return True
    return False


# ── The minute timer (manage.py tick) ───────────────────────────────────────────────────────────

def tick(now=None):
    """Reminders, expiry and the forwarder check. Returns what it did, for the log."""
    now = now or timezone.now()
    store = StoreSettings.load()
    done = {'reminded': 0, 'expired': 0, 'alerted': False}

    due = Order.objects.filter(status=Order.Status.AWAITING, reminder_sent_at=None, expires_at__gt=now,
                               created_at__lte=now - timedelta(minutes=store.reminder_minutes))
    for order in due:
        if Order.objects.filter(pk=order.pk, reminder_sent_at=None).update(reminder_sent_at=now):
            sms.send('reminder', order.phone, order, code=order.code, link=link(order))
            done['reminded'] += 1

    for order in Order.objects.filter(status=Order.Status.AWAITING, expires_at__lte=now):
        refresh(order)
        done['expired'] += 1

    done['alerted'] = _check_forwarder(store, now)
    return done


def _check_forwarder(store, now):
    """With automatic confirmation on, two or more orders in 3 hours running out with no claim and no
    automatic match since the first of them means the bank SMS aren't reaching cartbecart."""
    if settings.PAYMENT_PROVIDER != 'cartbecart' or not store.owner_mobile:
        return False
    window = now - timedelta(hours=3)
    silent = Order.objects.filter(status=Order.Status.EXPIRED, claimed_at=None, created_at__gte=window)
    first = silent.order_by('created_at').first()
    if silent.count() < 2 or Order.objects.filter(paid_via='auto', paid_at__gte=first.created_at).exists():
        return False
    if not cache.add('forwarder-alert', 1, 6 * 3600):  # once per 6 hours
        return False
    sms.send('owner_forwarder', store.owner_mobile, count=fa_digits(silent.count()))
    return True


# ── Returns (7 working days from delivery, e-commerce law art. 37) ──────────────────────────────

def return_deadline(order):
    """The last day a return can be asked for: return_days working days (Fridays off) after delivery,
    or after shipping + 3 days when staff never marked it delivered. Holidays aren't known, so this
    errs on the buyer's side by a day or two; staff can still accept a late one in the panel."""
    start = order.delivered_at or (order.shipped_at and order.shipped_at + timedelta(days=3))
    if not start:
        return None
    day, left = timezone.localtime(start).date(), StoreSettings.load().return_days
    while left:
        day += timedelta(days=1)
        if day.weekday() != 4:  # Friday
            left -= 1
    return day


def request_return(order, data):
    deadline = return_deadline(order)
    if order.status not in (Order.Status.SHIPPED, Order.Status.DELIVERED) or not deadline:
        raise OrderError('return_not_yet')
    if timezone.localdate() > deadline:
        raise OrderError('return_closed')
    if order.returns.exclude(status=ReturnRequest.Status.REJECTED).exists():
        raise OrderError('return_exists')
    ret = ReturnRequest.objects.create(order=order, reason=data['reason'], sheba=data['sheba'],
                                       account_holder=data['holder'])
    audit('return_requested', order, detail=data['reason'][:200])
    return ret


def return_received(ret, user):
    if type(ret).objects.filter(pk=ret.pk, status=ret.Status.REQUESTED).update(
            status=ret.Status.RECEIVED, received_at=timezone.now()):
        audit('return_received', ret.order, user)
        sms.send('return_received', ret.order.phone, ret.order, code=ret.order.code)
        return True
    return False


def refund(ret, user, reference):
    if type(ret).objects.filter(pk=ret.pk, status__in=(ret.Status.REQUESTED, ret.Status.RECEIVED)).update(
            status=ret.Status.REFUNDED, refund_reference=reference, refunded_at=timezone.now()):
        audit('refunded', ret.order, user, reference)
        sms.send('refunded', ret.order.phone, ret.order, code=ret.order.code, reference=reference)
        return True
    return False


def reject_return(ret, user, reason=''):
    if type(ret).objects.filter(pk=ret.pk, status__in=(ret.Status.REQUESTED, ret.Status.RECEIVED)).update(
            status=ret.Status.REJECTED):
        audit('return_rejected', ret.order, user, reason)
        return True
    return False
