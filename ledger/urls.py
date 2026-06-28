from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'accounts', views.AccountViewSet)
router.register(r'transactions', views.TransactionViewSet)
router.register(r'entries', views.JournalEntryViewSet)
router.register(r'payments', views.PaymentSplitViewSet, basename='payments')

urlpatterns = [
    path('', include(router.urls)),
]
