"""
The staff panel's JSON API under /api/panel/ (the React panel is at /panel). Sign-in is Django's
session; changes need the CSRF token from session/.

Roles (manage.py setup_roles):
- Staff: orders and returns: see them, prepare, ship, mark delivered, mark a return received, notes.
- Owners: also approve or reject payments and cancel orders (shop.approve_payment), record refunds
  (shop.refund), and edit the store: price, fees, cards, texts (shop.change_storesettings).
Every change is in the order's history (AuditLog) with who did it.
"""
import json
import mimetypes
import re
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.db.models import Count, Max, Q, Sum
from django.http import FileResponse, Http404, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import orders, persian
from .models import AuditLog, Card, Color, Faq, Order, Page, PaymentEvent, Product, ReturnRequest, SmsLog, StoreSettings
from .views import PRODUCT_SLUG

LOGIN_LIMIT = (10, 15 * 60)  # attempts per address per 15 minutes
PAGE_SIZE = 30
S = Order.Status

QUEUES = {
    'action': (S.REVIEW, S.PAID, S.PREPARING),
    'review': (S.REVIEW,),
    'awaiting': (S.AWAITING,),
    'to_ship': (S.PAID, S.PREPARING),
    'shipped': (S.SHIPPED,),
    'delivered': (S.DELIVERED,),
    'closed': (S.EXPIRED, S.CANCELLED),
}


def _error(code, status=400, **extra):
    return JsonResponse({'error': code, **extra}, status=status)


def _json(request):
    try:
        data = json.loads(request.body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _ip(request):
    return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '')


def _limited(key, limit):
    count, seconds = limit
    cache.add(key, 0, timeout=seconds)
    try:
        return cache.incr(key) > count
    except ValueError:
        return False


def is_staff(user):
    return user.is_authenticated and user.is_active and (
        user.is_superuser or user.groups.filter(name__in=('Owners', 'Staff')).exists())


def abilities(user):
    return {
        'approve': user.has_perm('shop.approve_payment'),
        'refund': user.has_perm('shop.refund'),
        'manage': user.has_perm('shop.change_storesettings'),
    }


def staff(perm=None):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not is_staff(request.user):
                return _error('signed_out', 401)
            if perm and not request.user.has_perm(perm):
                return _error('forbidden', 403)
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def _user(user):
    return {'username': user.username, 'name': user.get_full_name() or user.username, 'can': abilities(user)}


# ── Session ─────────────────────────────────────────────────────────────────────────────────────

@require_GET
def session(request):
    return JsonResponse({'csrf': get_token(request), 'user': _user(request.user) if is_staff(request.user) else None})


@require_POST
def sign_in(request):
    if _limited(f'login:{_ip(request)}', LOGIN_LIMIT):
        return _error('too_many', 429)
    data = _json(request)
    user = authenticate(request, username=str(data.get('username', '')).strip(), password=data.get('password', ''))
    if not user or not is_staff(user):
        return _error('credentials', 401)
    login(request, user)
    cache.delete(f'login:{_ip(request)}')
    return JsonResponse({'csrf': get_token(request), 'user': _user(user)})


@require_POST
def sign_out(request):
    logout(request)
    return JsonResponse({'csrf': get_token(request)})


# ── Orders ──────────────────────────────────────────────────────────────────────────────────────

def _row(order):
    return {
        'id': order.id, 'code': order.code, 'status': order.status, 'status_label': order.get_status_display(),
        'name': order.name, 'phone': order.phone, 'city': order.city, 'amount_rial': order.amount_rial,
        'shipping': order.get_shipping_display(), 'is_gift': order.is_gift, 'color': order.color_name,
        'created': order.created_at.isoformat(), 'paid_at': order.paid_at.isoformat() if order.paid_at else None,
        'claimed': bool(order.claimed_at),
    }


@require_GET
@staff()
def summary(request):
    for order in Order.objects.filter(status=S.AWAITING, expires_at__lte=timezone.now()):
        orders.refresh(order)
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    counts = dict(Order.objects.values_list('status').annotate(n=Count('id')))
    paid_today = Order.objects.filter(paid_at__gte=today)
    last_auto = Order.objects.filter(paid_via='auto').order_by('-paid_at').values_list('paid_at', flat=True).first()
    return JsonResponse({
        'counts': counts,
        'returns_open': ReturnRequest.objects.filter(status__in=('requested', 'received')).count(),
        'unmatched': PaymentEvent.objects.filter(outcome__in=('unmatched', 'unparsed', 'mismatch'),
                                                 created_at__gte=timezone.now() - timedelta(days=7)).count(),
        'paid_today': {'count': paid_today.count(), 'rial': paid_today.aggregate(s=Sum('amount_rial'))['s'] or 0},
        'last_auto_match': last_auto.isoformat() if last_auto else None,
        'provider': settings.PAYMENT_PROVIDER,
    })


@require_GET
@staff()
def order_list(request):
    queue = request.GET.get('queue', 'action')
    found = Order.objects.all()
    if queue in QUEUES:
        statuses = QUEUES[queue]
        if queue == 'action' and settings.PAYMENT_PROVIDER == 'manual':
            statuses += (S.AWAITING,)  # nothing confirms them automatically: staff must look
        found = found.filter(status__in=statuses)
    q = persian.clean_text(request.GET.get('q', ''))
    if q:
        digits = persian.latin_digits(q)
        found = found.filter(Q(code__iexact=digits) | Q(phone__contains=digits) | Q(name__icontains=q)
                             | Q(tracking_code__iexact=digits) | Q(provider_ref__iexact=digits)
                             | Q(transfers__provider_ref__iexact=digits)).distinct()
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except ValueError:
        page = 1
    total = found.count()
    rows = found[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
    return JsonResponse({'orders': [_row(o) for o in rows], 'total': total, 'page': page, 'page_size': PAGE_SIZE})


def _detail(order):
    data = _row(order)
    data.update({
        'token': order.token, 'province': order.province, 'address': order.address,
        'postal_code': order.postal_code, 'product': order.product_name,
        'price_rial': order.unit_price_rial, 'shipping_rial': order.shipping_rial, 'offset_rial': order.offset_rial,
        'shipping_on_delivery': order.shipping_on_delivery, 'pay_in_rial': order.pay_in_rial,
        'provider_ref': order.provider_ref,  # cartbecart's CBC-… code, to find it in their dashboard
        'card': {'bank': order.card_bank, 'number': order.card_number, 'holder': order.card_holder},
        # Paid in several card-to-card transfers (over the bank's cap): each one, its own CBC-… code.
        'transfers': [{'position': t.position, 'amount_rial': t.amount_rial, 'offset_rial': t.offset_rial,
                       'card': {'bank': t.card_bank, 'number': t.card_number}, 'provider_ref': t.provider_ref,
                       'status': t.status, 'status_label': t.get_status_display(),
                       'paid_at': t.paid_at.isoformat() if t.paid_at else None} for t in order.transfers.all()],
        'expires': order.expires_at.isoformat(), 'paid_via': order.paid_via,
        'confirmed_by': order.confirmed_by.get_full_name() or order.confirmed_by.username if order.confirmed_by else None,
        'claim': {
            'reference': order.claim_reference, 'last4': order.claim_card_last4, 'time': order.claim_time,
            'note': order.claim_note, 'file': bool(order.claim_file),
            'at': order.claimed_at.isoformat() if order.claimed_at else None,
        },
        'tracking': order.tracking_code, 'staff_note': order.staff_note,
        'shipped_at': order.shipped_at.isoformat() if order.shipped_at else None,
        'delivered_at': order.delivered_at.isoformat() if order.delivered_at else None,
        'history': [{'action': a.action, 'detail': a.detail, 'at': a.created_at.isoformat(),
                     'user': (a.user.get_full_name() or a.user.username) if a.user else None}
                    for a in order.audit.select_related('user')],
        'sms': [{'kind': m.kind, 'text': m.text, 'status': m.status, 'error': m.error, 'at': m.created_at.isoformat()}
                for m in order.sms.all()],
        'payments': [{'source': e.source, 'amount_rial': e.amount_rial, 'outcome': e.outcome,
                      'at': e.created_at.isoformat()} for e in order.payment_events.all()],
        'returns': [_return_row(r) for r in order.returns.all()],
    })
    return data


@require_GET
@staff()
def order_detail(request, pk):
    order = orders.refresh(get_object_or_404(Order, pk=pk))
    return JsonResponse(_detail(order))


@require_POST
@staff()
def order_action(request, pk):
    order = orders.refresh(get_object_or_404(Order, pk=pk))
    data = _json(request)
    action, user = data.get('action'), request.user
    needs = {'approve': 'shop.approve_payment', 'reject': 'shop.approve_payment', 'cancel': 'shop.approve_payment'}
    if action in needs and not user.has_perm(needs[action]):
        return _error('forbidden', 403)
    if action == 'approve':
        ok = orders.mark_paid(order, 'manual', user, persian.clean_text(data.get('note'), 200))
    elif action == 'reject':
        ok = orders.reject_payment(order, user, persian.clean_text(data.get('note'), 200))
    elif action == 'preparing':
        ok = orders.set_preparing(order, user)
    elif action == 'ship':
        tracking = persian.latin_digits(persian.clean_text(data.get('tracking'), 40))
        if len(tracking) < 4:
            return _error('tracking')
        ok = orders.ship(order, user, tracking)
    elif action == 'deliver':
        ok = orders.deliver(order, user)
    elif action == 'cancel':
        ok = orders.cancel(order, user, persian.clean_text(data.get('note'), 200))
    elif action == 'note':
        order.staff_note = str(data.get('note', ''))[:2000]
        order.save(update_fields=['staff_note'])
        orders.audit('note', order, user)
        ok = True
    else:
        return _error('action')
    if not ok:
        return _error('state')  # someone else changed it first; the panel reloads
    order.refresh_from_db()
    return JsonResponse(_detail(order))


@require_GET
@staff()
def claim_file(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not order.claim_file:
        raise Http404
    kind = mimetypes.guess_type(order.claim_file.name)[0] or 'application/octet-stream'
    response = FileResponse(order.claim_file.open('rb'), content_type=kind)
    response['Cache-Control'] = 'private, no-store'
    return response


@require_GET
@staff()
def slip(request, pk):
    """Packing slip + address label, printed from the browser. A gift's slip has no prices."""
    order = get_object_or_404(Order, pk=pk)
    return render(request, 'shop/slip.html', {
        'order': order, 'price': persian.toman(order.unit_price_rial),
        'shipping': 'پس‌کرایه' if order.shipping_on_delivery else persian.toman(order.shipping_rial) + ' تومان'
        if order.shipping_rial else 'رایگان',
        'total': persian.toman(order.amount_rial),
    })


# ── Returns and payment events ──────────────────────────────────────────────────────────────────

def _return_row(ret):
    return {
        'id': ret.id, 'order_id': ret.order_id, 'code': ret.order.code, 'name': ret.order.name,
        'status': ret.status, 'status_label': ret.get_status_display(), 'reason': ret.reason, 'sheba': ret.sheba,
        'holder': ret.account_holder, 'reference': ret.refund_reference, 'created': ret.created_at.isoformat(),
        'amount_rial': ret.order.unit_price_rial,
    }


@require_GET
@staff()
def return_list(request):
    found = ReturnRequest.objects.select_related('order')
    if request.GET.get('open') == '1':
        found = found.filter(status__in=('requested', 'received'))
    return JsonResponse({'returns': [_return_row(r) for r in found[:100]]})


@require_POST
@staff()
def return_action(request, pk):
    ret = get_object_or_404(ReturnRequest.objects.select_related('order'), pk=pk)
    data = _json(request)
    action = data.get('action')
    if action in ('refund', 'reject') and not request.user.has_perm('shop.refund'):
        return _error('forbidden', 403)
    if action == 'received':
        ok = orders.return_received(ret, request.user)
    elif action == 'refund':
        reference = persian.latin_digits(persian.clean_text(data.get('reference'), 40))
        if len(reference) < 4:
            return _error('reference')
        ok = orders.refund(ret, request.user, reference)
    elif action == 'reject':
        ok = orders.reject_return(ret, request.user, persian.clean_text(data.get('note'), 200))
    else:
        return _error('action')
    if not ok:
        return _error('state')
    ret.refresh_from_db()
    return JsonResponse(_return_row(ret))


@require_GET
@staff()
def payment_events(request):
    found = PaymentEvent.objects.select_related('order')[:100]
    return JsonResponse({'events': [
        {'id': e.id, 'source': e.source, 'amount_rial': e.amount_rial, 'outcome': e.outcome,
         'order': {'id': e.order_id, 'code': e.order.code} if e.order else None,
         'payload': e.payload, 'at': e.created_at.isoformat()} for e in found
    ]})


@require_GET
@staff()
def sms_log(request):
    return JsonResponse({'sms': [
        {'phone': m.phone, 'kind': m.kind, 'text': m.text if m.kind != 'otp' else 'کد تأیید (پنهان)',
         'status': m.status, 'error': m.error, 'at': m.created_at.isoformat(), 'order': m.order_id}
        for m in SmsLog.objects.all()[:100]
    ]})


# ── Store settings (owners) ─────────────────────────────────────────────────────────────────────

STORE_FIELDS = ('store_name', 'tagline', 'phone', 'email', 'address', 'postal_code', 'hours', 'instagram',
                'owner_mobile', 'shipping_post_rial', 'shipping_tipax_rial', 'tipax_on_delivery', 'post_days', 'tipax_days',
                'payment_minutes', 'reminder_minutes', 'return_days', 'transfer_limit_rial', 'enamad_html')
# The cap for one card-to-card: 0 (never split) or at least 10M toman, so an order splits into a few round
# 5M transfers at most (orders.split_amounts).
TRANSFER_LIMIT_MIN_RIAL = 100_000_000
PRODUCT_FIELDS = ('name', 'subtitle', 'description', 'price_rial', 'is_available', 'specs')


def _panel_product(slug):
    """The model being edited: the one named (?product=), else the main bag."""
    product = Product.objects.filter(slug=slug).first() if slug else None
    return product or Product.objects.filter(slug=PRODUCT_SLUG).first() or Product.objects.order_by('id').first()


def _settings_json(product):
    store = StoreSettings.load()
    return {
        'store': {f: getattr(store, f) for f in STORE_FIELDS},
        'product': {'slug': product.slug, **{f: getattr(product, f) for f in PRODUCT_FIELDS}} if product else None,
        # Every model, the main bag first; another one shows on the site once it has a price.
        'products': [{'slug': p.slug, 'name': p.name, 'main': p.slug == PRODUCT_SLUG, 'on_sale': bool(p.price_rial)}
                     for p in sorted(Product.objects.all(), key=lambda p: (p.slug != PRODUCT_SLUG, p.id))],
    }


@require_http_methods(['GET', 'POST'])
@staff('shop.change_storesettings')
def store_settings(request):
    if request.method == 'GET':
        return JsonResponse(_settings_json(_panel_product(request.GET.get('product'))))
    data = _json(request)
    store = StoreSettings.load()
    errors = {}
    for field in STORE_FIELDS:
        if field not in data.get('store', {}):
            continue
        value = data['store'][field]
        model_field = StoreSettings._meta.get_field(field)
        if model_field.get_internal_type() in ('PositiveBigIntegerField', 'PositiveSmallIntegerField'):
            try:
                value = int(persian.latin_digits(str(value)))  # str: latin_digits(0) is ''
                if value < 0 or (field == 'transfer_limit_rial' and 0 < value < TRANSFER_LIMIT_MIN_RIAL):
                    raise ValueError
            except (TypeError, ValueError):
                errors[field] = 'number'
                continue
        elif model_field.get_internal_type() == 'BooleanField':
            value = bool(value)
        elif field == 'owner_mobile':
            if value and not persian.phone(value):
                errors[field] = 'phone'
                continue
            value = persian.phone(value) if value else ''
        elif field != 'enamad_html':
            value = persian.clean_text(value, model_field.max_length)
        setattr(store, field, value)
    product_data = data.get('product') or {}
    product = _panel_product(product_data.get('slug'))
    if product and product_data:
        before = product.price_rial
        for field in PRODUCT_FIELDS:
            if field not in product_data:
                continue
            value = product_data[field]
            if field == 'price_rial':
                try:
                    value = int(persian.latin_digits(str(value)))  # str: latin_digits(0) is ''
                    # 0 keeps another model off the site (no price yet); the main bag always has one.
                    if value < 0 or (value == 0 and product.slug == PRODUCT_SLUG):
                        raise ValueError
                except (TypeError, ValueError):
                    errors['price_rial'] = 'number'
                    continue
            elif field == 'is_available':
                value = bool(value)
            elif field == 'specs':
                value = [[persian.clean_text(a, 60), persian.clean_text(b, 200)] for a, b in value
                         if persian.clean_text(a)] if isinstance(value, list) else product.specs
            else:
                value = persian.clean_text(value, None if field == 'description' else
                                           Product._meta.get_field(field).max_length)
            setattr(product, field, value)
    if errors:
        return _error('fields', fields=errors)
    store.save()
    if product and product_data:
        product.save()
        if product.price_rial != before:
            orders.audit('price', None, request.user,
                         f'{product.name}: {persian.toman(before)} → {persian.toman(product.price_rial)} تومان')
    orders.audit('settings', None, request.user)
    return JsonResponse(_settings_json(product))


def _card_json(card):
    return {'id': card.id, 'bank': card.bank, 'number': card.number, 'holder': card.holder, 'active': card.active,
            'last_used_at': card.last_used_at.isoformat() if card.last_used_at else None, 'position': card.position}


@require_http_methods(['GET', 'POST'])
@staff('shop.change_storesettings')
def cards(request):
    if request.method == 'POST':
        data = _json(request)
        card = get_object_or_404(Card, pk=data['id']) if data.get('id') else Card()
        if data.get('delete') and card.pk:
            if card.orders.exists():
                card.active = False  # orders point at it: keep it, just stop using it
                card.save(update_fields=['active'])
            else:
                card.delete()
        else:
            number = persian.card_number(data.get('number'))
            bank, holder = persian.clean_text(data.get('bank'), 40), persian.clean_text(data.get('holder'), 80)
            errors = {k: 'required' for k, v in (('bank', bank), ('holder', holder)) if not v}
            if not number:
                errors['number'] = 'card'
            if errors:
                return _error('fields', fields=errors)
            card.bank, card.number, card.holder = bank, number, holder
            card.active = bool(data.get('active', True))
            card.save()
        orders.audit('cards', None, request.user)
    return JsonResponse({'cards': [_card_json(c) for c in Card.objects.all()]})


def _color_json(color):
    return {'id': color.id, 'name': color.name, 'swatch': color.swatch, 'shown': color.shown,
            'available': color.available, 'position': color.position, 'orders': color.orders.count()}


@require_http_methods(['GET', 'POST'])
@staff('shop.change_storesettings')
def colors(request):
    """A model's colours (?product=, else the main bag's). The site asks for a colour only while more than one
    is shown."""
    product = _panel_product(request.GET.get('product'))
    if request.method == 'POST':
        data = _json(request)
        color = get_object_or_404(Color, pk=data['id'], product=product) if data.get('id') else Color(product=product)
        if data.get('delete') and color.pk:
            if color.orders.exists():
                color.shown = False  # orders name it: keep it, just take it off the site
                color.save(update_fields=['shown'])
            else:
                color.delete()
        else:
            name = persian.clean_text(data.get('name'), 40)
            swatch = str(data.get('swatch') or '').strip().lower()
            errors = {}
            if not name:
                errors['name'] = 'required'
            if not re.fullmatch(r'#[0-9a-f]{6}', swatch):
                errors['swatch'] = 'swatch'
            if errors:
                return _error('fields', fields=errors)
            color.name, color.swatch = name, swatch
            color.shown, color.available = bool(data.get('shown', True)), bool(data.get('available', True))
            if not color.pk:
                color.position = (product.colors.aggregate(m=Max('position'))['m'] or 0) + 1
            color.save()
        orders.audit('colors', None, request.user)
    return JsonResponse({'colors': [_color_json(c) for c in product.colors.all()] if product else []})


@require_http_methods(['GET', 'POST'])
@staff('shop.change_storesettings')
def texts(request):
    """Policy pages and FAQs."""
    if request.method == 'POST':
        data = _json(request)
        kind = data.get('kind')
        if kind == 'page':
            page = get_object_or_404(Page, pk=data.get('id'))
            page.title = persian.clean_text(data.get('title'), 120) or page.title
            page.body = str(data.get('body', ''))[:20000]
            page.save()
        elif kind == 'faq':
            faq = get_object_or_404(Faq, pk=data['id']) if data.get('id') else Faq()
            if data.get('delete') and faq.pk:
                faq.delete()
            else:
                faq.question = persian.clean_text(data.get('question'), 200)
                faq.answer = str(data.get('answer', ''))[:5000]
                faq.published = bool(data.get('published', True))
                if not faq.question:
                    return _error('fields', fields={'question': 'required'})
                if not faq.pk:
                    faq.position = (Faq.objects.order_by('-position').values_list('position', flat=True).first() or 0) + 1
                faq.save()
        else:
            return _error('kind')
        orders.audit('texts', None, request.user, kind)
    return JsonResponse({
        'pages': [{'id': p.id, 'slug': p.slug, 'title': p.title, 'body': p.body} for p in Page.objects.all()],
        'faqs': [{'id': f.id, 'question': f.question, 'answer': f.answer, 'published': f.published} for f in Faq.objects.all()],
    })


@require_GET
@staff()
def activity(request):
    """Store-wide history (settings, price, cards), newest first."""
    return JsonResponse({'items': [
        {'action': a.action, 'detail': a.detail, 'at': a.created_at.isoformat(),
         'user': (a.user.get_full_name() or a.user.username) if a.user else None,
         'order': {'id': a.order_id, 'code': a.order.code} if a.order else None}
        for a in AuditLog.objects.select_related('user', 'order')[:100]
    ]})
