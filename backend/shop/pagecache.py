"""The home and policy pages, cached for a minute. Rendering them was most of the server's work in the
load test (about 26 ms of CPU each on the shared server, against about 2 ms from the cache). Any change
to what they show empties the cache, so staff edits appear at once."""
from django.core.cache import caches
from django.db.models.signals import post_delete, post_save
from django.views.decorators.cache import cache_page

SECONDS = 60

cached = cache_page(SECONDS, cache='pages')


def clear(**kwargs):
    caches['pages'].clear()


def connect():
    """Called from ShopConfig.ready(): every model the cached pages read from."""
    from .models import Card, Color, Faq, Page, Product, StoreSettings

    for model in (Card, Color, Faq, Page, Product, StoreSettings):
        post_save.connect(clear, sender=model, dispatch_uid=f'pagecache-save-{model.__name__}')
        post_delete.connect(clear, sender=model, dispatch_uid=f'pagecache-delete-{model.__name__}')
