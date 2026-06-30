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

    # M-Pesa webhooks (called by Safaricom)
    path('webhooks/mpesa/c2b/', mpesa.c2b_callback, name='mpesa-c2b'),
    path('webhooks/mpesa/b2c/', mpesa.b2c_callback, name='mpesa-b2c'),
    path('webhooks/mpesa/timeout/', mpesa.timeout_callback, name='mpesa-timeout'),
]
