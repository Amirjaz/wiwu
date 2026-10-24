from django.urls import path

from . import panel, views

urlpatterns = [
    path('', views.home, name='home'),
    path('checkout/', views.checkout, name='checkout'),
    path('o/<str:token>/', views.order_page, name='order'),
    path('orders/', views.lookup_page, name='lookup'),
    path('p/<slug:slug>/', views.page, name='page'),
    path('robots.txt', views.robots),
    path('sitemap.xml', views.sitemap),
    path('panel/', views.panel_shell, name='panel'),
    path('panel/slip/<int:pk>/', panel.slip, name='slip'),
    path('panel/<path:rest>', views.panel_shell),

    path('api/otp/', views.api_otp),
    path('api/orders/', views.api_place),
    path('api/orders/<str:token>/', views.api_order),
    path('api/orders/<str:token>/claim/', views.api_claim),
    path('api/orders/<str:token>/sheba/', views.api_sheba),
    path('api/orders/<str:token>/return/', views.api_return),
    path('api/lookup/', views.api_lookup),
    path('api/payments/cartbecart/', views.cartbecart_webhook),

    path('api/panel/session/', panel.session),
    path('api/panel/login/', panel.sign_in),
    path('api/panel/logout/', panel.sign_out),
    path('api/panel/summary/', panel.summary),
    path('api/panel/orders/', panel.order_list),
    path('api/panel/orders/<int:pk>/', panel.order_detail),
    path('api/panel/orders/<int:pk>/action/', panel.order_action),
    path('api/panel/orders/<int:pk>/claim-file/', panel.claim_file),
    path('api/panel/returns/', panel.return_list),
    path('api/panel/returns/<int:pk>/action/', panel.return_action),
    path('api/panel/payments/', panel.payment_events),
    path('api/panel/sms/', panel.sms_log),
    path('api/panel/settings/', panel.store_settings),
    path('api/panel/cards/', panel.cards),
    path('api/panel/shebas/', panel.shebas),
    path('api/panel/colors/', panel.colors),
    path('api/panel/texts/', panel.texts),
    path('api/panel/activity/', panel.activity),
]
