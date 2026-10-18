from django.apps import AppConfig


class ShopConfig(AppConfig):
    name = 'shop'
    verbose_name = 'فروشگاه'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import pagecache
        pagecache.connect()
