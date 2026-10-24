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
# The hero's pictures, in the slider's order (frontend/public/images/look/, the originals in
# media/source-photos/look/). Amir's photo of the man with the bag opens it, for 3 seconds only (Amir,
# 2026-10-21); then posters of the bag alone (black, black and brown side by side as mirror images, brown,
# and after each colour both versions of it, the two-zipper bag beside the Alpha, 2026-10-23; silver dropped
# 2026-10-21, the client doesn't have it): WiWU's studio renders on a dark studio
# sweep (tools/hero_slides.py), drawn twice, tall for phones (<name>-600/-1200.webp) and wide for laptops
# (<name>-wide-1600/-2560.webp), the bags clear of the headline. Amir's photos (2:3) fill the screen on
# phones and stand beside the headline at their own shape on laptops (a stretched photo was blurry there).
# Each: name, alt text, the point kept in view when the picture fills a frame of another shape (CSS
# object-position) on tall screens and on wide ones, whether it's a photo, the colour (as named in the
# panel) a hero colour dot jumps to, and its time on screen if not the slider's 6 seconds.
LOOK = [
    {'name': 'in-the-car', 'alt': 'مردی با کیف ویوو آلفا در دست، داخل خودرو',
     'focus': '50% 62%', 'wide': '50% 50%', 'photo': True, 'time': 3},
    {'name': 'bag-black', 'alt': 'کیف ویوو آلفا مشکی، با قفل اثر انگشت و پلاک برند',
     'focus': '0% 50%', 'wide': '0% 50%', 'color': 'مشکی'},
    {'name': 'bag-black-duo', 'alt': 'کیف ویوو مشکی در دو مدل، دو زیپ و تک‌زیپ، کنار هم',
     'focus': '0% 50%', 'wide': '0% 50%'},
    {'name': 'bag-colors', 'alt': 'کیف ویوو آلفا در دو رنگ مشکی و قهوه‌ای، کنار هم',
     'focus': '0% 50%', 'wide': '0% 50%'},
    {'name': 'plate', 'alt': 'نمای نزدیک کیف ویوو آلفا در دست: چرم دانه‌دار و پلاک فلزی برند',
     'focus': '50% 45%', 'wide': '50% 50%', 'photo': True},
    {'name': 'bag-brown', 'alt': 'کیف ویوو آلفا قهوه‌ای، با قفل اثر انگشت و پلاک برند',
     'focus': '0% 50%', 'wide': '0% 50%', 'color': 'قهوه‌ای'},
    {'name': 'bag-brown-duo', 'alt': 'کیف ویوو قهوه‌ای در دو مدل، دو زیپ و تک‌زیپ، کنار هم',
     'focus': '0% 50%', 'wide': '0% 50%'},
]

CLAIM_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif', 'application/pdf'}


def _product():
    return Product.objects.filter(slug=PRODUCT_SLUG).first() or Product.objects.first()


def _on_sale(slug):
    """The model a buyer asked for (?product=): any with a price; a model without one isn't on the site yet."""
    product = Product.objects.filter(slug=slug).first() if slug else None
    return product if product and product.price_rial else None


# What the home page says about another model, from its specs: these rows if it has them, else its first four.
HIGHLIGHTS = ('زیپ‌ها', 'ابعاد', 'بند', 'وزن')


# Each model's short name beside its pictures (bag_pictures) and at checkout, and its version where both
# are named side by side (the closing section's prices); another model's full name otherwise.
SHORT_NAMES = {'alpha': 'آلفا، تک‌زیپ', 'phantom-pro': 'فانتوم پرو، دو زیپ'}
VERSIONS = {'alpha': 'تک‌زیپ', 'phantom-pro': 'دو زیپ'}
# Both versions in one colour, side by side (tools/duo_pictures.py), by the colour's name in the panel.
DUO_PICTURES = {'مشکی': 'images/colors/duo-black.webp', 'قهوه‌ای': 'images/colors/duo-brown.webp'}


def colour_cards(main, others):
    """The closing section's cards (Amir, 2026-10-23): one per colour of the main bag, showing every model
    that comes in it (by the colour's name) in one picture, with each one's price. A card opens checkout in
    its colour, where the version is picked."""
    cards = []
    for color in main.shown_colors():
        versions = [main] + [o['product'] for o in others
                             if any(c.name == color.name for c in o['product'].shown_colors())]
        both = len(versions) > 1 and color.name in DUO_PICTURES
        cards.append({'color': color, 'picture': DUO_PICTURES[color.name] if both else color.photo, 'both': both,
                      'versions': [(VERSIONS.get(p.slug, p.name), persian.toman(p.price_rial)) for p in versions]
                      if both else []})
    return cards


def bag_pictures(main, others):
    """The bags pictured in the parts section (Amir, 2026-10-23: pictures instead of the 3D bag): every model on
    sale in every colour on show that has a picture, the main bag first, each with its price."""
    bags = []
    for product in [main] + [other['product'] for other in others]:
        for color in product.shown_colors():
            if color.photo:
                bags.append({'product': product, 'color': color, 'model': SHORT_NAMES.get(product.slug, product.name),
                             'price': persian.toman(product.price_rial)})
    return bags


def lineup(main):
    """The other models on sale beside the main bag, for their own section on the home page."""
    others = []
    for product in Product.objects.exclude(pk=main.pk).order_by('id'):
        if not product.price_rial:
            continue
        rows = [row for row in product.specs if row[0] in HIGHLIGHTS] or product.specs[:4]
        others.append({'product': product, 'price': persian.toman(product.price_rial),
                       'colors': product.shown_colors(), 'highlights': rows[:4]})
    return others


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


def _store_json(store, product, models):
    return {
        'store': store.store_name,
        # Every model on sale, the main bag first; the buyer picks one when there's more than one (Amir,
        # 2026-10-23: one zipper or two), starting from the one asked for (?product=).
        'models': [{'slug': m.slug, 'name': m.name, 'short': VERSIONS.get(m.slug, m.name),
                    'price_rial': m.price_rial, 'available': m.is_available,
                    # Only asked for when more than one colour is on show.
                    'colors': [{'id': c.id, 'name': c.name, 'swatch': c.swatch, 'available': c.available}
                               for c in m.shown_colors()]}
                   for m in models],
        'start': product.slug,
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
    models = lineup(product)
    dims, spec_cells = _specs(product)
    # The sample bill's total: price, the first shipping option and 437 of the per-order offset, which is
    # rials with cartbecart (they make amounts unique to the rial) and tomans without.
    in_rial = payments.enabled()
    example = product.price_rial + (shipping[0]['price_rial'] if shipping else 0) + (437 if in_rial else 4370)
    return render(request, 'shop/home.html', {
        'product': product, 'faqs': faqs, 'price': persian.toman(product.price_rial),
        'shipping': shipping, 'example_total': persian.rial(example) if in_rial else persian.toman(example),
        'look': LOOK, 'parts': PARTS, 'colors': product.shown_colors(), 'models': models,
        'bags': bag_pictures(product, models), 'cards': colour_cards(product, models),
        'dims': dims, 'spec_cells': spec_cells,
        'jsonld': _jsonld(request, store, product, faqs),
    })


# The parts, a tab per side of the bag (id, name, and its photo: file, width, height). Each part: x and y
# on the photo as percentages (strings, so the template doesn't localise them), a name, a note, where
# the number goes on the photo when it would hide what it points at (x in %, beside the bag, joined by
# a line), and its pin on the 3D bag: the point, and the way that surface faces (the pin hides when it
# turns away), in the model's metres (frontend/src/bag3d/scene.ts). Since the 3D bag left the page
# (2026-10-23) only the names and notes show; the rest stays for if it comes back.
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
    store, main = StoreSettings.load(), _product()
    product = _on_sale(request.GET.get('product')) or main
    models = [main] + [other['product'] for other in lineup(main)]
    # The summary beside the form: each model's name and price and its bag in each colour; checkout.tsx shows
    # the picked model's, in the picked colour (the first until one is).
    summaries = [{'product': m, 'price': persian.toman(m.price_rial), 'colors': m.shown_colors()} for m in models]
    return render(request, 'shop/checkout.html', {
        'product': product, 'summaries': summaries, 'island': _store_json(store, product, models),
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
    if data.get('product') and data['product'] != product.slug:  # another model, if it's on sale
        product = _on_sale(data['product'])
        if product is None:
            return _error('unavailable')
    try:
        color = orders.pick_color(product, data.get('color'))
        otp_id = orders.check_otp(clean['phone'], persian.latin_digits(data.get('code', '')))
    except OrderError as exc:
        return _error(exc.code, **exc.extra)
    try:
        order = orders.place(product, clean, _ip(request), color=color)
    except OrderError as exc:
        orders.release_otp(otp_id)  # not the buyer's fault: the same code works when they try again
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
        'pay_in_rial': order.pay_in_rial,
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
def cartbecart_webhook(request):
    """cartbecart's events (payments.py). 2xx tells them it arrived; anything else and they send it
    again (30 s, 2 min, 10 min, 1 h, 6 h later)."""
    if not payments.enabled():
        raise Http404
    if not payments.signature_ok(request.body, request.headers.get('X-CBC-Timestamp'),
                                 request.headers.get('X-CBC-Signature')):
        return JsonResponse({'error': 'signature'}, status=401)
    event = orders.cartbecart_event(request.body)
    return JsonResponse({'ok': True, 'outcome': event.outcome})


@require_GET
@ensure_csrf_cookie
def panel_shell(request, rest=''):
    """The staff panel (React, its own sign-in). Never indexed, whatever SITE_NOINDEX says."""
    response = render(request, 'shop/panel.html')
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response
