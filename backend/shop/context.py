"""What every page's template gets: the store's details and the footer's pages."""
from django.conf import settings

from .models import Card, Order, Page, StoreSettings


def _card_holder(auto_confirm):
    """Whose card buyers pay into: with cartbecart, the holder of the card it gave the latest order."""
    if auto_confirm:
        holder = Order.objects.exclude(provider_token='').values_list('card_holder', flat=True).first()
        if holder:
            return holder
    return Card.objects.filter(active=True).values_list('holder', flat=True).first() or ''


def store(request):
    auto_confirm = settings.PAYMENT_PROVIDER == 'cartbecart'
    return {
        'store': StoreSettings.load(),
        'footer_pages': Page.objects.only('slug', 'title'),
        'noindex': settings.NOINDEX,
        'public_url': settings.PUBLIC_URL,
        # Payments confirm themselves (cartbecart) or wait for staff; the copy says which.
        'auto_confirm': auto_confirm,
        'card_holder': _card_holder(auto_confirm),
    }
