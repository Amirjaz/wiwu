"""{% icon 'fingerprint' 'size-5' %}, and the filters toman, fa (Persian digits), jalali and jsonld."""
import json
from functools import lru_cache

from django import template
from django.template.loader import get_template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .. import jalali, persian

register = template.Library()


@lru_cache(maxsize=64)
def _svg(name):
    return get_template(f'shop/icons/{name}.svg').template.source.strip()


@register.simple_tag
def icon(name, classes=''):
    """A Phosphor icon (copied by frontend/scripts/copy-icons.mjs), decorative."""
    return format_html('<span class="icon {}" aria-hidden="true">{}</span>', classes, mark_safe(_svg(name)))


@register.filter
def toman(rial):
    return persian.toman(rial or 0)


@register.filter
def rial(amount):
    return persian.rial(amount or 0)


@register.filter
def fa(value):
    return persian.fa_digits(value)


@register.filter(name='jalali')
def jalali_filter(moment):
    return jalali.long(moment) if moment else ''


@register.filter
def jsonld(data):
    """JSON for a <script type="application/ld+json">; '<' escaped so text can't close the script."""
    return mark_safe(json.dumps(data, ensure_ascii=False).replace("<", chr(92) + "u003c"))
