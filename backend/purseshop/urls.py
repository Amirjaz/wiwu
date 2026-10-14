from django.contrib import admin
from django.urls import include, path

admin.site.site_header = admin.site.site_title = 'فروشگاه — مدیریت'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('shop.urls')),
]
