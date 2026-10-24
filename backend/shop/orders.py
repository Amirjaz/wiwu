"""
What happens to an order, in one place. Views and the panel call these; nothing else changes an
order's status.

    awaiting_payment ──(cartbecart: paid)───────────► paid ─► preparing ─► shipped ─► delivered
          │      └──(buyer: "I've paid")──► needs_review ─(staff approve)─┘    │
          │                                       └─(staff reject)─► cancelled  │
          └──(window over)──► expired ──(paid in their grace hour / claim)──►   └─► return request

With cartbecart (payments.py) they choose the amount and card and report the result; without it the
shop chooses them and staff confirm every payment.

An order over the bank's cap for one card-to-card transfer is paid in several (split_amounts, Transfer),
each with its own exact amount: it's paid once all have arrived, and goes to review if the window ends
with only some.
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
from django.db.models import Q
from django.utils import timezone

from . import payments, sms
from .models import (AuditLog, Card, Color, Order, OtpCode, PaymentEvent, ReturnRequest, StoreSettings, Transfer,
                     new_order_code, new_order_token)
from .persian import bank_of, fa_digits, money, toman

log = logging.getLogger(__name__)

OPEN = (Order.Status.AWAITING, Order.Status.REVIEW)
LATE_MATCH_HOURS = 48  # money for an expired order still finds it this long after it was placed
OFFSET_MAX_TOMAN = 999
SPLIT_MARGIN_RIAL = 10_000  # room under the cap for the offset: up to 999 rials with cartbecart, 999 tomans without
SPLIT_PART_RIAL = 50_000_000  # the round transfers split off an order over the cap: 5M toman (Amir, 2026-10-24)

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


def release_otp(otp_id):
    """Gives a used code back when the order couldn't be placed for a reason that isn't the buyer's,
    so pressing the button again works without a new SMS."""
    OtpCode.objects.filter(pk=otp_id).update(used_at=None)


def check_otp(phone, code):
    """Uses up the phone's latest live code if it matches (returns its id); raises otherwise."""
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
    return otp.pk


# ── Placing an order ────────────────────────────────────────────────────────────────────────────

def _amounts_in_use():
    """Amounts a payment could still arrive for: open orders and their transfers, and recently expired ones."""
    since = timezone.now() - timedelta(hours=LATE_MATCH_HOURS)
    live = Q(status__in=OPEN) | Q(status=Order.Status.EXPIRED, created_at__gte=since)
    return set(Order.objects.filter(live).values_list('amount_rial', flat=True)) | set(
        Transfer.objects.filter(order__in=Order.objects.filter(live)).values_list('amount_rial', flat=True))


def choose_amount(base_rial, also_taken=()):
    """base + a random 1…999 toman no open order has, so a bank deposit points at exactly one order.
    The buyer pays the extra (decided 2026-10-14). also_taken: amounts just given to the same order's
    other transfers."""
    taken = _amounts_in_use() | set(also_taken)
    free = [t * 10 for t in range(1, OFFSET_MAX_TOMAN + 1) if base_rial + t * 10 not in taken]
    if not free:
        raise OrderError('busy')
    offset = random.choice(free)
    return offset, base_rial + offset


def split_amounts(base_rial, limit_rial):
    """What an order of base_rial is paid in, before each transfer's offset: one transfer when it fits under
    the bank's cap for one card-to-card (limit_rial; 0 for none); above it the rest first, then round
    5-million-toman transfers, as few as keep the first under the cap (Amir, 2026-10-24: 16.5M toman is
    11.5M + 5M with a 15M cap)."""
    room = limit_rial - SPLIT_MARGIN_RIAL
    if not limit_rial or base_rial <= room or room < SPLIT_PART_RIAL:
        return [base_rial]
    count = -(-(base_rial - room) // SPLIT_PART_RIAL)  # round transfers needed, rounded up
    return [base_rial - count * SPLIT_PART_RIAL] + [SPLIT_PART_RIAL] * count


def amount_text(order):
    """The amount to pay, with its unit, as SMS and the log say it: one, or each transfer's."""
    transfers = list(order.transfers.all())
    if not transfers:
        return money(order.amount_rial, order.pay_in_rial)
    in_rial = order.pay_in_rial
    return ' و '.join(money(t.amount_rial, in_rial) for t in transfers) + f' (در {fa_digits(len(transfers))} واریز جدا)'


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
    fields = dict(
        phone=data['phone'], name=data['name'], province=data['province'], city=data['city'],
        address=data['address'], postal_code=data['postal_code'], shipping=data['shipping'],
        is_gift=data['is_gift'], product=product, product_name=product.name,
        color=color, color_name=color.name if color else '',
        unit_price_rial=product.price_rial, shipping_rial=shipping_rial,
        shipping_on_delivery=store.shipping_on_delivery(data['shipping']), ip=ip,
    )
    parts = split_amounts(product.price_rial + shipping_rial, store.transfer_limit_rial)
    order = _place_cartbecart(parts, fields) if payments.enabled() else _place_manual(parts, fields, store)
    amount = amount_text(order)
    refs = '، '.join(t.provider_ref for t in order.transfers.all() if t.provider_ref) or order.provider_ref
    audit('placed', order, detail=f'{amount}، کارت …{order.card_number[-4:]}' + (f'، کارت‌به‌کارت {refs}' if refs else ''))
    minutes = max(1, round((order.expires_at - timezone.now()).total_seconds() / 60))
    sms.send('order_created', order.phone, order, code=order.code, amount=amount, link=link(order),
             minutes=fa_digits(minutes))
    return order


def _place_manual(parts, fields, store):
    """The shop picks the amounts and the card (see choose_amount, _next_card); parts from split_amounts."""
    for _ in range(5):
        try:
            # IMMEDIATE transactions (settings) serialise writers, so two buyers can't get one amount.
            with transaction.atomic():
                picks = []
                for part in parts:
                    offset, amount = choose_amount(part, [a for _, a in picks])
                    picks.append((offset, amount))
                card = _next_card()
                expires = timezone.now() + timedelta(minutes=store.payment_minutes)
                order = Order.objects.create(
                    **fields, offset_rial=sum(o for o, _ in picks), amount_rial=sum(a for _, a in picks), card=card,
                    card_bank=card.bank, card_number=card.number, card_holder=card.holder, expires_at=expires,
                )
                if len(picks) > 1:
                    Transfer.objects.bulk_create([
                        Transfer(order=order, position=i, amount_rial=amount, offset_rial=offset, card=card,
                                 card_bank=card.bank, card_number=card.number, card_holder=card.holder, expires_at=expires)
                        for i, (offset, amount) in enumerate(picks, 1)])
                return order
        except IntegrityError:  # code or token collision: try new ones
            continue
    raise OrderError('busy')


def _registered_card(reg):
    """The card cartbecart chose, as the order keeps it. Staff may have it in the panel, with its bank's name."""
    card = Card.objects.filter(number=reg['card_number']).first()
    return dict(card=card, card_bank=card.bank if card else bank_of(reg['card_number']), card_number=reg['card_number'],
                card_holder=reg['card_holder'] or (card.holder if card else ''))


def _place_cartbecart(parts, fields):
    """cartbecart picks the amounts and the card, one registration per transfer (merchant_order_id the
    order's code, or "<code>-<n>" for each of several). Their calls are made outside any transaction, so a
    slow answer doesn't hold up other buyers' writes."""
    for _ in range(5):
        code, token = new_order_code(), new_order_token()
        if not Order.objects.filter(Q(code=code) | Q(token=token)).exists():
            break
    regs = []
    try:
        for i, part in enumerate(parts, 1):
            regs.append(payments.create_order(code if len(parts) == 1 else f'{code}-{i}', part,
                                              f'{settings.PUBLIC_URL}/o/{token}/', fields['name'], fields['phone']))
    except payments.CartbecartError as exc:  # any registered already just run out unpaid
        log.warning('cartbecart refused order %s: %s', code, exc)
        _payment_down(exc)
        raise OrderError('payment_down') from None
    first = regs[0]
    try:
        with transaction.atomic():
            order = Order.objects.create(
                **fields, code=code, token=token, **_registered_card(first),
                offset_rial=sum(r['amount_rial'] for r in regs) - sum(parts),
                amount_rial=sum(r['amount_rial'] for r in regs), expires_at=min(r['expires_at'] for r in regs),
                provider_token=first['token'] if len(regs) == 1 else '',
                provider_ref=first['ref'] if len(regs) == 1 else '',
            )
            if len(regs) > 1:
                Transfer.objects.bulk_create([
                    Transfer(order=order, position=i, amount_rial=reg['amount_rial'], offset_rial=reg['amount_rial'] - part,
                             expires_at=reg['expires_at'], provider_token=reg['token'], provider_ref=reg['ref'],
                             **_registered_card(reg))
                    for i, (reg, part) in enumerate(zip(regs, parts), 1)])
            return order
    except IntegrityError:  # a code taken in the moment between: their orders just run out unpaid
        raise OrderError('busy') from None


def _payment_down(exc):
    """No order can be placed until the owner fixes it on cartbecart's side (no default card, plan,
    monthly quota, key), so tell them, once an hour."""
    audit('payment_down', detail=str(exc)[:300])
    owner = StoreSettings.load().owner_mobile
    if owner and cache.add('payment-down-alert', 1, 3600):
        sms.send('owner_payment_down', owner, status=str(exc.status or 'ارتباط'))


# ── Payment ─────────────────────────────────────────────────────────────────────────────────────

def refresh(order):
    """Expire the order if its window is over (the minute timer does this too; pages can't wait). One paid
    in several transfers that has only some of them goes to review instead: money came, staff sort it out
    (the rest may still arrive and pay it, or the buyer gets a refund)."""
    if order.status == Order.Status.AWAITING and timezone.now() >= order.expires_at:
        arrived = order.transfers.filter(status=Transfer.Status.PAID).count()
        if arrived:
            to_review(order, f'فقط {fa_digits(arrived)} واریز از {fa_digits(order.transfers.count())} واریز رسید')
            return order
        updated = Order.objects.filter(pk=order.pk, status=Order.Status.AWAITING).update(status=Order.Status.EXPIRED)
        if updated:
            order.status = Order.Status.EXPIRED
            audit('expired', order)
    return order


def mark_paid(order, via, user=None, detail=''):
    with transaction.atomic():
        now = timezone.now()
        updated = Order.objects.filter(pk=order.pk, status__in=OPEN + (Order.Status.EXPIRED,)).update(
            status=Order.Status.PAID, paid_at=now, paid_via=via,
            confirmed_by=user if user and user.is_authenticated else None,
        )
        if updated:  # staff confirming by hand saw every transfer
            order.transfers.exclude(status=Transfer.Status.PAID).update(status=Transfer.Status.PAID, paid_at=now)
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


# ── cartbecart's results (payments.py) ──────────────────────────────────────────────────────────

CARTBECART_GRACE = timedelta(minutes=90)  # after expires_at they still match late bank SMS (60 min, with margin)
SYNC_EVERY = 120  # seconds between two status checks of one order
SYNC_MAX = 20  # status checks per minute


def provider_result(order, status, reason=''):
    """What cartbecart says about one of our orders, from a webhook or a status check. Returns the
    outcome for the payments log."""
    refresh(order)
    if status == 'paid':
        if mark_paid(order, 'auto'):
            return 'matched'
        if order.status == Order.Status.CANCELLED:
            # Money matched to an order staff had cancelled: refund it, or reopen the order.
            audit('paid_after_cancel', order, detail='کارت‌به‌کارت واریز این سفارش لغوشده را تأیید کرد')
            owner = StoreSettings.load().owner_mobile
            if owner:
                sms.send('owner_review', owner, order, code=order.code)
            return 'late'
        return 'noop'
    if status == 'needs_review':
        if order.status not in (Order.Status.AWAITING, Order.Status.EXPIRED):
            return 'noop'  # already in review (or settled): the status check would say so every 2 minutes
        why = 'کارت‌به‌کارت: واریزی رسید که دقیقاً با مبلغ نمی‌خواند؛ در داشبورد کارت‌به‌کارت تأیید یا رد کنید'
        return 'review' if to_review(order, why) else 'noop'
    if status == 'expired' and reason and reason != 'timeout':
        # rejected_by_merchant / rejected_by_operator: money came and was refused in their dashboard.
        if Order.objects.filter(pk=order.pk, status__in=OPEN + (Order.Status.EXPIRED,)).update(
                status=Order.Status.CANCELLED):
            order.refresh_from_db()
            audit('payment_rejected', order, detail=f'رد در کارت‌به‌کارت ({reason})')
            sms.send('payment_not_found', order.phone, order, code=order.code, link=link(order))
            return 'rejected'
        return 'noop'
    if status == 'expired':
        return 'expired' if order.status == Order.Status.EXPIRED else 'noop'  # refresh() has expired it if due
    if status == 'cancelled':
        if Order.objects.filter(pk=order.pk, status__in=OPEN + (Order.Status.EXPIRED,)).update(
                status=Order.Status.CANCELLED):
            audit('cancelled', order, detail='لغو در داشبورد کارت‌به‌کارت')
            return 'cancelled'
        return 'noop'
    return 'ignored'


TRANSFER_STATUS = {'paid': Transfer.Status.PAID, 'needs_review': Transfer.Status.REVIEW,
                   'expired': Transfer.Status.EXPIRED, 'cancelled': Transfer.Status.CANCELLED}


def transfer_result(transfer, status, reason=''):
    """What cartbecart says about one transfer of an order paid in several. The last to arrive pays the
    order; one arriving alone after the window, or refused while another has arrived, puts it in review.
    Otherwise the order goes as a single one would (provider_result). Returns the outcome for the log
    ('part' for a transfer that arrived while others are still missing)."""
    order = refresh(transfer.order)
    which = f'واریز {fa_digits(transfer.position)} از {fa_digits(order.transfers.count())}'
    if status == 'paid':
        if not Transfer.objects.filter(pk=transfer.pk).exclude(status=Transfer.Status.PAID).update(
                status=Transfer.Status.PAID, paid_at=timezone.now()):
            return 'noop'
        audit('transfer_paid', order, detail=f'{which}: {money(transfer.amount_rial, order.pay_in_rial)}')
        if not order.transfers.exclude(status=Transfer.Status.PAID).exists():
            return provider_result(order, 'paid')
        if order.status == Order.Status.EXPIRED:
            to_review(order, f'کارت‌به‌کارت {which} را پس از مهلت تأیید کرد؛ واریز دیگر نرسیده')
        elif order.status == Order.Status.CANCELLED:
            return provider_result(order, 'paid')  # money for a cancelled order: 'late', the owner is told
        return 'part'
    if status not in TRANSFER_STATUS:
        return 'ignored'
    Transfer.objects.filter(pk=transfer.pk).exclude(status=Transfer.Status.PAID).update(status=TRANSFER_STATUS[status])
    refused = status == 'cancelled' or (status == 'expired' and reason and reason != 'timeout')
    if refused and order.transfers.filter(status=Transfer.Status.PAID).exists():
        why = f'کارت‌به‌کارت {which} را رد یا لغو کرد، ولی واریز دیگری رسیده؛ برگرداندن یا تکمیل پول را پیگیری کنید'
        return 'review' if to_review(order, why) else 'noop'
    return provider_result(order, status, reason)


def _find(code):
    """The order, and the transfer if it's one of several, cartbecart means by a merchant_order_id."""
    if not code or code.startswith('TEST-'):
        return None, None
    order = Order.objects.filter(code=code).first()
    if order is None:
        prefix, _, position = code.rpartition('-')
        if prefix and position.isdigit():
            transfer = Transfer.objects.select_related('order').filter(order__code=prefix, position=int(position)).first()
            if transfer:
                return transfer.order, transfer
    return order, None


def cartbecart_event(body):
    """One webhook call, its signature already checked. Returns the PaymentEvent (unsaved for a repeat)."""
    event = payments.parse_event(body)
    if event is None:
        return PaymentEvent.objects.create(
            source='cartbecart', outcome='unparsed', payload={'raw': (body or b'')[:2000].decode('utf-8', 'replace')})
    if event['event_id'] and PaymentEvent.objects.filter(source='cartbecart', provider_ref=event['event_id']).exists():
        return PaymentEvent(source='cartbecart', outcome='repeat')  # "at least once": seen it already
    order, transfer = _find(event['code'])
    expected = transfer or order
    record = PaymentEvent(source='cartbecart', order=order, amount_rial=event['amount_rial'],
                          provider_ref=event['event_id'], payload=event['payload'])
    if order is None:
        # manage.py cartbecart_check's test orders, or an order that isn't this site's.
        record.outcome = 'test' if event['code'].startswith('TEST-') else 'unmatched'
    elif (event['amount_rial'] and event['amount_rial'] != expected.amount_rial) or (
            event['ref'] and expected.provider_ref and event['ref'] != expected.provider_ref):
        to_review(order, f'کارت‌به‌کارت درباره‌ی سفارش دیگری با همین کد خبر داد ({event["ref"]})')
        record.outcome = 'mismatch'
    elif event['status'] is None:
        record.outcome = 'ignored'
    elif transfer:
        record.outcome = transfer_result(transfer, event['status'], event['reason'])
    else:
        record.outcome = provider_result(order, event['status'], event['reason'])
    record.save()
    return record


def sync_cartbecart(now=None):
    """The minute timer's backup for a missed webhook: asks cartbecart about our orders whose result
    could still change (each at most every SYNC_EVERY seconds). Returns how many changed."""
    now = now or timezone.now()
    waiting = (Order.objects.filter(~Q(provider_token='') | Q(transfers__provider_token__gt=''))
               .filter(Q(status=Order.Status.AWAITING)
                       | Q(status=Order.Status.EXPIRED, expires_at__gte=now - CARTBECART_GRACE)
                       | Q(status=Order.Status.REVIEW, created_at__gte=now - timedelta(days=7)))
               .distinct().order_by('created_at'))
    changed = checked = 0
    for order in waiting:
        if checked >= SYNC_MAX:
            break
        if not cache.add(f'cartbecart-sync:{order.pk}', 1, SYNC_EVERY):
            continue
        # Each transfer still missing, for an order paid in several; else the order itself.
        targets = [t for t in order.transfers.exclude(status=Transfer.Status.PAID) if t.provider_token]
        if not targets and order.provider_token:
            targets = [None]
        for transfer in targets:
            checked += 1
            try:
                status = payments.order_status((transfer or order).provider_token).get('status')
            except payments.CartbecartError as exc:
                log.warning('cartbecart status of %s: %s', transfer or order.code, exc)
                if exc.status in (None, 429):  # unreachable, or too many calls: try again next minute
                    return changed
                continue
            if status in ('paid', 'needs_review'):
                outcome = transfer_result(transfer, status) if transfer else provider_result(order, status)
                if outcome in ('matched', 'review', 'late', 'part'):
                    PaymentEvent.objects.create(
                        source='cartbecart', order=order, amount_rial=(transfer or order).amount_rial, outcome=outcome,
                        payload={'status': status, 'via': 'status check',
                                 **({'transfer': transfer.position} if transfer else {})})
                    changed += 1
            order.refresh_from_db()
            if order.status not in OPEN + (Order.Status.EXPIRED,):
                break
    return changed


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
