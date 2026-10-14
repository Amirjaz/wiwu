"""What every page's template gets: the store's details and the footer's pages."""
from django.conf import settings

from .models import Card, Page, StoreSettings


def store(request):
    return {
        'store': StoreSettings.load(),
        'footer_pages': Page.objects.only('slug', 'title'),
        'noindex': settings.NOINDEX,
        'public_url': settings.PUBLIC_URL,
        # Payments confirm themselves (cartbecart) or wait for staff; the copy says which.
        'auto_confirm': settings.PAYMENT_PROVIDER == 'cartbecart',
        'card_holder': Card.objects.filter(active=True).values_list('holder', flat=True).first() or '',
    }
