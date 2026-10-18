"""Django admin: the fallback for everything the panel (/panel) doesn't cover, and for users and roles."""
from django.contrib import admin

from .models import AuditLog, Card, Color, Faq, Order, Page, PaymentEvent, Product, ReturnRequest, SmsLog, StoreSettings

admin.site.register(StoreSettings)


class ColorInline(admin.TabularInline):
    model = Color
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ColorInline]

admin.site.register(Page)
admin.site.register(Faq)


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('bank', 'number', 'holder', 'active', 'last_used_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('code', 'status', 'name', 'phone', 'color_name', 'amount_rial', 'created_at')
    list_filter = ('status', 'shipping')
    search_fields = ('code', 'phone', 'name', 'tracking_code')
    readonly_fields = ('token', 'created_at')


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'created_at')


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ('source', 'amount_rial', 'outcome', 'order', 'created_at')
    list_filter = ('outcome',)


@admin.register(SmsLog)
class SmsLogAdmin(admin.ModelAdmin):
    list_display = ('phone', 'kind', 'status', 'created_at')
    list_filter = ('kind', 'status')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'order', 'user', 'created_at')
    list_filter = ('action',)
