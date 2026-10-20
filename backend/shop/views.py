"""
Pages (rendered here, so search engines, Torob and link previews see real content) and the buyer's
JSON API under /api/. The React islands on the pages talk to the API.
"""
import json
import logging
import re

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from . import jalali, orders, pagecache, payments, persian, text
from .models import Faq, Order, Page, Product, StoreSettings
from .orders import OrderError

log = logging.getLogger(__name__)

PRODUCT_SLUG = 'alpha'
PROVINCES = [
    'آذربایجان شرقی', 'آذربایجان غربی', 'اردبیل', 'اصفهان', 'البرز', 'ایلام', 'بوشهر', 'تهران',
    'چهارمحال و بختیاری', 'خراسان جنوبی', 'خراسان رضوی', 'خراسان شمالی', 'خوزستان', 'زنجان', 'سمنان',
    'سیستان و بلوچستان', 'فارس', 'قزوین', 'قم', 'کردستان', 'کرمان', 'کرمانشاه', 'کهگیلویه و بویراحمد',
    'گلستان', 'گیلان', 'لرستان', 'مازندران', 'مرکزی', 'هرمزگان', 'همدان', 'یزد',
]
# The hero's photos, in the slider's order (frontend/public/images/look/<name>-160/-600/-1200.webp, the
# originals in media/source-photos/look/): name, alt text, and the point kept in view when the photo
# fills a frame of another shape (CSS object-position): on tall screens, and on wide ones, where only a
# band of the tall photo shows, around the bag.
#   The bag-only slides show the other colours: WiWU's studio renders on a dark studio backdrop
# (media/source-photos/look/bag-*.jpg, 2026-10-20), the bag left of centre so the headline stays clear.
LOOK = [
    ('by-the-car', 'کیف دستی ویوو آلفا در دست، کنار در باز خودرویی با صندلی‌های قرمز', '50% 40%', '50% 50%'),
    ('bag-brown', 'کیف ویوو آلفا قهوه‌ای، با قفل اثر انگشت و پلاک برند', '0% 50%', '50% 25%'),
    ('plate', 'نمای نزدیک کیف ویوو آلفا در دست: چرم دانه‌دار و پلاک فلزی برند', '50% 45%', '50% 36%'),
    ('bag-silver', 'کیف ویوو آلفا سفید نقره‌ای، با قفل اثر انگشت', '0% 50%', '50% 25%'),
    ('low-angle', 'کیف ویوو آلفا در دست، از زاویه‌ی پایین، با درختان پاییزی پشت سر', '50% 50%', '50% 50%'),
    ('bag-brown-back', 'پشت کیف ویوو آلفا قهوه‌ای: جیب زیپ‌دار و بند مچی', '0% 50%', '50% 25%'),
    ('in-the-car', 'کیف ویوو آلفا جلوی دوربین، داخل خودرو', '50% 62%', '50% 62%'),
    ('seated', 'کیف ویوو آلفا در دست، نشسته کنار خودرو', '50% 58%', '50% 56%'),
    ('door', 'کیف ویوو آلفا در دست، با کت چرمی و شلوار جین کنار خودرو', '50% 38%', '50% 28%'),
]

CLAIM_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif', 'application/pdf'}


def _product():
    return Product.objects.filter(slug=PRODUCT_SLUG).first() or Product.objects.first()


def _ip(request):
    return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR') or None


def _error(code, status=400, **extra):
    return JsonResponse({'error': code, **extra}, status=status)


def _json(request):
    try:
        data = json.loads(request.body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _store_json(store, product):
    return {
        'store': store.store_name,
        'product': {'name': product.name, 'price_rial': product.price_rial, 'available': product.is_available},
        # Only asked for when more than one colour is on show.
        'colors': [{'id': c.id, 'name': c.name, 'swatch': c.swatch, 'available': c.available}
                   for c in product.shown_colors()],
        'shipping': store.shipping_options(),
        'provinces': PROVINCES,
        'payment_minutes': store.payment_minutes,
        'return_days': store.return_days,
        'dev_sms': settings.SMS_BACKEND == 'console',
    }


# ── Pages ───────────────────────────────────────────────────────────────────────────────────────

@require_GET
@pagecache.cached
def home(request):
    store, product = StoreSettings.load(), _product()
    if product is None:
        raise Http404('no product yet: run manage.py seed_store')
    faqs = list(Faq.objects.filter(published=True))
    for faq in faqs:
        faq.html = text.render(faq.answer)
    shipping = store.shipping_options()
    dims, spec_cells = _specs(product)
    # The sample bill's total: price, the first shipping option and 437 toman of the per-order offset.
    example = product.price_rial + (shipping[0]['price_rial'] if shipping else 0) + 4370
    return render(request, 'shop/home.html', {
        'product': product, 'faqs': faqs, 'price': persian.toman(product.price_rial),
        'shipping': shipping, 'example_total': persian.toman(example),
        'look': LOOK, 'parts': PARTS, 'colors': product.shown_colors(),
        'dims': dims, 'spec_cells': spec_cells,
        'jsonld': _jsonld(request, store, product, faqs),
    })


# The parts, a tab per side of the bag (id, name, and its photo: file, width, height). Each part: x and y
# on the photo as percentages (strings, so the template doesn't localise them), a name, a note, where
# the number goes on the photo when it would hide what it points at (x in %, beside the bag, joined by
# a line), and its pin on the 3D bag: the point, and the way that surface faces (the pin hides when it
# turns away), in the model's metres (frontend/src/bag3d/scene.ts).
PARTS = [
    ('front', 'روبه‌رو', 'images/front.webp', 960, 588, [
        ('82.2', '78.5', 'پلاک برند', 'پلاک فلزی برند ویوو روی رویه‌ی جلو.', '70',
         '0.0636 0.0342 0.0364', '0.07 0.05 0.99'),
        ('40', '50', 'رویه‌ی جلو', 'چرم مصنوعی دانه‌دار، مثل پشت کیف.', '',
         '-0.025 0.07 0.0296', '0 0.2 0.98'),
        ('50', '2', 'زیپ اصلی', 'زیپ فلزی بالای کیف.', '',
         '-0.003 0.1415 0.0002', '0 0.92 0.39'),
    ]),
    ('side', 'کنار', 'images/side.webp', 448, 752, [
        ('54.5', '77.8', 'حسگر اثر انگشت', 'تا ۱۰ اثر انگشت؛ حدود نیم ثانیه تا باز شدن.', '-8',
         '-0.13036 0.0389 -0.00235', '-0.9958 0.0296 -0.0864'),
        ('54', '69', 'چراغ وضعیت', 'وقتی قفل باز می‌شود سبز می‌شود.', '-8',
         '-0.13003 0.0489 -0.00275', '-0.9958 0.0296 -0.0864'),
        ('55', '53', 'جای سرِ زیپ', 'سرِ زیپ اصلی اینجا قفل می‌شود.', '-8',
         '-0.12965 0.06279 -0.00229', '-0.9958 0.0296 -0.0864'),
        ('55', '17', 'زیپ اصلی', 'از بالای کیف تا ماژول قفل.', '-8',
         '-0.1223 0.102 0.0002', '-0.9 0.08 0.42'),
    ]),
    ('back', 'پشت', 'images/back.webp', 960, 555, [
        ('86', '42', 'جیب زیپ‌دار پشت', 'جدا از قفل اصلی؛ برای کارت مترو، بلیت و رسید.', '',
         '-0.08 0.093 -0.0235', '-0.05 0.31 -0.95'),
        ('45', '2.5', 'زیپ اصلی', 'دور بالای کیف؛ سرِ آن در ماژول قفل جا می‌خورد و قفل می‌شود.', '',
         '0.012 0.1416 -0.0002', '0 0.92 -0.39'),
        ('30', '84', 'بند مچی', 'پشت کیف، تا کیف از دستتان سُر نخورد.', '',
         '0.05 0.034 -0.0373', '0.03 0.06 -1'),
        ('76.7', '85', 'دکمه فلزی', 'بند مچی با این دکمه بسته می‌شود.', '',
         '-0.0875 0.0295 -0.0365', '0.11 0.03 -0.99'),
        ('42', '58', 'چرم مصنوعی دانه‌دار', 'PU، مقاوم در برابر آب و خط و خش؛ با یک دستمال تمیز می‌شود.', '',
         '0.02 0.065 -0.0314', '0.01 0.18 -0.98'),
    ]),
]


def _specs(product):
    """The size's three numbers (drawn on the photos, when the size spec has them) and the other specs."""
    specs = [tuple(pair) for pair in product.specs]
    size = next((value for label, value in specs if label == 'ابعاد'), '')
    dims = re.findall(r'[۰-۹]+(?:٫[۰-۹]+)?', size)
    if len(dims) != 3:
        return [], specs
    return dims, [s for s in specs if s[0] != 'ابعاد']


def _jsonld(request, store, product, faqs):
    data = [{
        '@context': 'https://schema.org', '@type': 'Product', 'name': product.name,
        'description': product.subtitle, 'sku': product.slug, 'brand': {'@type': 'Brand', 'name': 'WiWU'},
        'image': [f'{settings.PUBLIC_URL}/images/{n}.webp' for n in ('front', 'back', 'side')] +
                 [f'{settings.PUBLIC_URL}/{c.photo}' for c in product.shown_colors() if c.photo],
        'offers': {
            '@type': 'Offer', 'url': settings.PUBLIC_URL + '/', 'priceCurrency': 'IRR', 'price': product.price_rial,
            'availability': 'https://schema.org/' + ('InStock' if product.is_available else 'OutOfStock'),
            'seller': {'@type': 'Organization', 'name': store.store_name},
        },
    }]
    if faqs:
        data.append({
            '@context': 'https://schema.org', '@type': 'FAQPage',
            'mainEntity': [{'@type': 'Question', 'name': f.question,
                            'acceptedAnswer': {'@type': 'Answer', 'text': f.answer}} for f in faqs],
        })
    return data


@require_GET
@ensure_csrf_cookie
def checkout(request):
    store, product = StoreSettings.load(), _product()
    return render(request, 'shop/checkout.html', {
        'product': product, 'price': persian.toman(product.price_rial), 'island': _store_json(store, product),
        'colors': product.shown_colors(),
    })


@require_GET
@ensure_csrf_cookie
def order_page(request, token):
    order = get_object_or_404(Order, token=token)
    return render(request, 'shop/order.html', {'order': order, 'island': {'token': token}})


@require_GET
@ensure_csrf_cookie
def lookup_page(request):
    return render(request, 'shop/lookup.html', {'island': {'dev_sms': settings.SMS_BACKEND == 'console'}})


@require_GET
@pagecache.cached
def page(request, slug):
    item = get_object_or_404(Page, slug=slug)
    return render(request, 'shop/page.html', {'page': item, 'body': text.render(item.body)})


@require_GET
def robots(request):
    if settings.NOINDEX:
        body = 'User-agent: *\nDisallow: /\n'
    else:
        body = (f'User-agent: *\nDisallow: /o/\nDisallow: /panel/\nDisallow: /api/\nDisallow: /admin/\n'
                f'Sitemap: {settings.PUBLIC_URL}/sitemap.xml\n')
    return HttpResponse(body, content_type='text/plain')


@require_GET
def sitemap(request):
    urls = [reverse('home')] + [reverse('page', args=[slug]) for slug in Page.objects.values_list('slug', flat=True)]
    body = ''.join(f'<url><loc>{settings.PUBLIC_URL}{u}</loc></url>' for u in urls)
    return HttpResponse('<?xml version="1.0" encoding="UTF-8"?>'
                        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>',
                        content_type='application/xml')


# ── Buyer API ───────────────────────────────────────────────────────────────────────────────────

@require_POST
def api_otp(request):
    phone = persian.phone(_json(request).get('phone'))
    if not phone:
        return _error('phone')
    try:
        wait, code = orders.send_otp(phone, _ip(request))
    except OrderError as exc:
        return _error(exc.code, 429 if exc.code in ('otp_wait', 'otp_limit') else 400, **exc.extra)
    data = {'ok': True, 'phone': phone, 'wait': wait}
    if settings.DEBUG and settings.SMS_BACKEND == 'console':
        data['dev_code'] = code  # local development only: no SMS is sent, so show the code
    return JsonResponse(data)


def _clean_checkout(data):
    """The checkout form, cleaned; (data, field errors)."""
    errors = {}
    clean = {
        'phone': persian.phone(data.get('phone')),
        'name': persian.clean_text(data.get('name'), 80),
        'province': persian.clean_text(data.get('province'), 40),
        'city': persian.clean_text(data.get('city'), 60),
        'address': persian.clean_text(data.get('address'), 400),
        'postal_code': persian.postal_code(data.get('postal_code')),
        'shipping': data.get('shipping'),
        'is_gift': bool(data.get('is_gift')),
    }
    if not clean['phone']:
        errors['phone'] = 'phone'
    if len(clean['name']) < 3:
        errors['name'] = 'required'
    if clean['province'] not in PROVINCES:
        errors['province'] = 'required'
    if len(clean['city']) < 2:
        errors['city'] = 'required'
    if len(clean['address']) < 10:
        errors['address'] = 'address'
    if not clean['postal_code']:
        errors['postal_code'] = 'postal_code'
    if clean['shipping'] not in Order.Shipping.values:
        errors['shipping'] = 'required'
    return clean, errors


@require_POST
def api_place(request):
    data = _json(request)
    clean, errors = _clean_checkout(data)
    if errors:
        return _error('fields', fields=errors)
    product = _product()
    try:
        color = orders.pick_color(product, data.get('color'))
        orders.check_otp(clean['phone'], persian.latin_digits(data.get('code', '')))
        order = orders.place(product, clean, _ip(request), color=color)
    except OrderError as exc:
        return _error(exc.code, **exc.extra)
    return JsonResponse({'token': order.token, 'url': reverse('order', args=[order.token])})


def order_json(order):
    order = orders.refresh(order)
    ret = order.returns.order_by('-created_at').first()
    deadline = orders.return_deadline(order)
    return {
        'code': order.code,
        'status': order.status,
        'status_label': order.get_status_display(),
        'created': order.created_at.isoformat(),
        'expires': order.expires_at.isoformat(),
        'now': timezone.now().isoformat(),
        'amount_rial': order.amount_rial,
        'price_rial': order.unit_price_rial,
        'shipping_rial': order.shipping_rial,
        'shipping_on_delivery': order.shipping_on_delivery,
        'offset_rial': order.offset_rial,
        'product': order.product_name,
        'color': order.color_name,
        'shipping': order.get_shipping_display(),
        'is_gift': order.is_gift,
        'name': order.name,
        'city': f'{order.province}، {order.city}',
        # The card is only shown while it's still worth paying into.
        'card': {'bank': order.card_bank, 'number': order.card_number, 'holder': order.card_holder}
        if order.status in (Order.Status.AWAITING, Order.Status.EXPIRED, Order.Status.REVIEW) else None,
        'claimed': bool(order.claimed_at),
        'tracking': order.tracking_code,
        'paid_at': order.paid_at.isoformat() if order.paid_at else None,
        'shipped_at': order.shipped_at.isoformat() if order.shipped_at else None,
        'return': {'status': ret.status, 'label': ret.get_status_display()} if ret else None,
        'can_return': bool(deadline) and order.status in (Order.Status.SHIPPED, Order.Status.DELIVERED)
        and not (ret and ret.status != ret.Status.REJECTED)
        and timezone.localdate() <= deadline,
        'return_until': jalali.day_label(deadline) if deadline else None,
    }


@require_GET
def api_order(request, token):
    return JsonResponse(order_json(get_object_or_404(Order, token=token)))


@require_POST
def api_claim(request, token):
    order = get_object_or_404(Order, token=token)
    data = request.POST
    upload = request.FILES.get('file')
    if upload:
        if upload.size > settings.UPLOAD_MAX_MB * 1024 * 1024:
            return _error('file_size')
        if upload.content_type not in CLAIM_TYPES:
            return _error('file_type')
    clean = {
        'reference': persian.latin_digits(persian.clean_text(data.get('reference'), 40)),
        'last4': ''.join(c for c in persian.latin_digits(data.get('last4', '')) if c.isdigit())[:4],
        'time': persian.clean_text(data.get('time'), 40),
        'note': persian.clean_text(data.get('note'), 300),
    }
    if not clean['reference'] and not upload:
        return _error('claim_empty')
    try:
        orders.claim(order, clean, upload)
    except OrderError as exc:
        return _error(exc.code)
    return JsonResponse(order_json(order))


@require_POST
def api_return(request, token):
    order = get_object_or_404(Order, token=token)
    data = _json(request)
    clean = {
        'reason': persian.clean_text(data.get('reason'), 1000),
        'sheba': persian.sheba(data.get('sheba')),
        'holder': persian.clean_text(data.get('holder'), 80),
    }
    errors = {}
    if len(clean['reason']) < 5:
        errors['reason'] = 'required'
    if not clean['sheba']:
        errors['sheba'] = 'sheba'
    if len(clean['holder']) < 3:
        errors['holder'] = 'required'
    if errors:
        return _error('fields', fields=errors)
    try:
        orders.request_return(order, clean)
    except OrderError as exc:
        return _error(exc.code)
    return JsonResponse(order_json(order))


@require_POST
def api_lookup(request):
    """A buyer who lost their link: phone + code → their orders (links included)."""
    data = _json(request)
    phone = persian.phone(data.get('phone'))
    if not phone:
        return _error('phone')
    try:
        orders.check_otp(phone, persian.latin_digits(data.get('code', '')))
    except OrderError as exc:
        return _error(exc.code)
    found = Order.objects.filter(phone=phone).order_by('-created_at')[:20]
    return JsonResponse({'orders': [
        {'code': o.code, 'status_label': o.get_status_display(), 'status': o.status,
         'created': o.created_at.isoformat(), 'amount_rial': o.amount_rial,
         'url': reverse('order', args=[o.token])}
        for o in found
    ]})


@csrf_exempt
@require_POST
def cartbecart_webhook(request, secret):
    if settings.PAYMENT_PROVIDER != 'cartbecart' or not payments.secret_ok(secret):
        raise Http404
    event = payments.webhook(request.body)
    return JsonResponse({'ok': True, 'outcome': event.outcome})


@require_GET
@ensure_csrf_cookie
def panel_shell(request, rest=''):
    """The staff panel (React, its own sign-in). Never indexed, whatever SITE_NOINDEX says."""
    response = render(request, 'shop/panel.html')
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response
