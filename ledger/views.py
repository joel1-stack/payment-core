import json
from decimal import Decimal
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from .models import Account, Transaction, JournalEntry, Merchant
from .serializers import AccountSerializer, TransactionSerializer, JournalEntrySerializer
from .services import SplitEngine
from providers.mock_provider import MockProvider
from providers import get_provider


# ── HTML pages ──

def landing(request):
    return render(request, 'ledger/landing.html')

def index(request):
    return render(request, 'ledger/index.html')


# ── Read-only views for raw ledger data ──

class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer


class JournalEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JournalEntry.objects.all()
    serializer_class = JournalEntrySerializer


# ── Helper ──

def _make_ref(prefix: str) -> str:
    return f"{prefix}_{Transaction.objects.count() + 1}"


# ── Merchants ──

class MerchantViewSet(viewsets.ViewSet):
    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        try:
            merchant = Merchant.objects.get(pk=pk)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)
        return Response(SplitEngine.merchant_dashboard(merchant))

    @action(detail=True, methods=['post'])
    def trigger_split(self, request, pk=None):
        try:
            merchant = Merchant.objects.get(pk=pk)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)
        amount = Decimal(str(request.data.get('amount', '1000')))
        phone = request.data.get('customer_phone', '254712345678')
        provider = MockProvider()
        payment = provider.charge(amount=amount, currency='KES', customer_ref=phone)
        result = SplitEngine.merchant_split(merchant, payment['reference'], amount)
        return Response({"provider": payment, "ledger": result}, status=201)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        try:
            merchant = Merchant.objects.get(pk=pk)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)
        ref = request.data.get('reference_id', _make_ref("CASH"))
        amount = Decimal(str(request.data.get('amount', 0)))
        result = SplitEngine.merchant_split(merchant, ref, amount, request.data.get('description', ''))
        return Response(result, status=201)

    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        try:
            merchant = Merchant.objects.get(pk=pk)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)
        dash = SplitEngine.merchant_dashboard(merchant)
        amount = Decimal(dash['available'])
        if amount <= 0:
            return Response({'error': 'No balance'}, status=400)
        ref = _make_ref("STL")
        SplitEngine.merchant_withdraw(merchant, ref)
        provider = MockProvider()
        payout = provider.payout(amount=amount, recipient=merchant.phone)
        return Response({"settled": str(amount), "to": merchant.phone, "ledger_ref": ref, "payout": payout})


# ── DEMO ENDPOINTS (used by the HTML page) ──

DEMO_REF = "TXN_DEMO_001"


@csrf_exempt
def trigger_split_demo(request):
    """POST /api/split/ — the HTML button calls this."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)

    # Check idempotency first
    if Transaction.objects.filter(reference_id=DEMO_REF).exists():
        return JsonResponse({"status": "already_processed"})

    # Get or create demo merchant
    from django.contrib.auth.models import User
    user, _ = User.objects.get_or_create(username="demo_user")
    merchant, _ = Merchant.objects.get_or_create(
        user=user, defaults={
            "business_name": "Demo Merchant",
            "phone": "254700000000",
            "platform_fee_percent": Decimal('5'),
        }
    )

    # Mock payment — no internet
    provider = MockProvider()
    payment = provider.charge(amount=Decimal("100"), currency="USD", customer_ref="demo_customer")

    # Record in the immutable ledger
    SplitEngine.merchant_split(merchant, DEMO_REF, Decimal("100"), "Demo payment")

    return JsonResponse({
        "status": "success",
        "reference": DEMO_REF,
        "amount": "100.00",
        "merchant_earns": "95.00",
        "platform_fee": "5.00",
    })


@api_view(['GET'])
def balances(request):
    """GET /api/balances/ — returns current ledger state for the HTML."""
    try:
        merchant = Merchant.objects.get(user__username="demo_user")
        dash = SplitEngine.merchant_dashboard(merchant)
        return Response({
            "merchant_available": float(Decimal(dash['available'])),
            "platform_revenue": float(Decimal(dash['fees_paid'])),
            "total_sales": float(Decimal(dash['total_sales'])),
            "ledger_balanced": dash['ledger_balanced'],
            "currency": dash['currency'],
        })
    except Merchant.DoesNotExist:
        return Response({
            "merchant_available": 0.0,
            "platform_revenue": 0.0,
            "total_sales": 0.0,
            "ledger_balanced": True,
            "currency": "USD",
        })


# ── Universal webhook ──

@csrf_exempt
def universal_webhook(request, provider_name):
    """
    POST /api/webhooks/universal/<provider_name>/
    Single webhook endpoint for all providers.
    Dispatches to the right provider's parse_callback, then fires the ledger.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    provider = get_provider(provider_name)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    result = provider.parse_callback(payload)
    if not result['success']:
        return JsonResponse({'status': 'failed', 'reason': result}, status=200)

    merchant = Merchant.objects.filter(
        user__username=result.get('our_reference', '')
    ).first()
    if not merchant:
        return JsonResponse({'status': 'no_merchant', 'reference': result.get('our_reference')})

    ledger_result = SplitEngine.merchant_split(
        merchant,
        result['reference'],
        result['amount'],
        f"Auto via {provider_name}",
    )
    return JsonResponse({'status': 'credited', 'ledger': ledger_result})


# ── Health ──

@api_view(['GET'])
def health(request):
    return Response({"status": "running", "engine": "payment-core", "ledger": SplitEngine.verify_ledger()})
