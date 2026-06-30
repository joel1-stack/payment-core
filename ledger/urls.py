from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import mpesa

router = DefaultRouter()
router.register(r'accounts', views.AccountViewSet)
router.register(r'transactions', views.TransactionViewSet)
router.register(r'entries', views.JournalEntryViewSet)
router.register(r'merchants', views.MerchantViewSet, basename='merchants')

urlpatterns = [
    path('', include(router.urls)),

    # Demo (used by the HTML page)
    path('split/', views.trigger_split_demo, name='split'),
    path('balances/', views.balances, name='balances'),

    # System
    path('health/', views.health, name='health'),

    # M-Pesa webhooks
    path('webhooks/mpesa/c2b/', mpesa.c2b_callback, name='mpesa-c2b'),
    path('webhooks/mpesa/b2c/', mpesa.b2c_callback, name='mpesa-b2c'),
    path('webhooks/mpesa/timeout/', mpesa.timeout_callback, name='mpesa-timeout'),

    # Universal webhook
    path('webhooks/universal/<str:provider_name>/', views.universal_webhook, name='universal-webhook'),
]
