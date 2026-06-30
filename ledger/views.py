from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Account, Transaction, JournalEntry, Merchant
from .serializers import AccountSerializer, TransactionSerializer, JournalEntrySerializer
from .services import SplitEngine
from .mpesa import stk_push, b2c_payment


class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer


class JournalEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JournalEntry.objects.all()
    serializer_class = JournalEntrySerializer


def _make_ref(prefix: str) -> str:
    return f"{prefix}_{Transaction.objects.count() + 1}"


class MerchantViewSet(viewsets.ViewSet):
    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        try:
            merchant = Merchant.objects.get(pk=pk)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=status.HTTP_404_NOT_FOUND)
        data = SplitEngine.merchant_dashboard(merchant)
        return Response(data)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """Record a cash/offline payment in the ledger."""
        try:
            merchant = Merchant.objects.get(pk=pk)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=status.HTTP_404_NOT_FOUND)
        data = request.data
        ref = data.get('reference_id')
        amount = Decimal(str(data.get('amount', 0)))
        if not ref:
            return Response({'error': 'reference_id required'}, status=status.HTTP_400_BAD_REQUEST)
        if Transaction.objects.filter(reference_id=ref).exists():
            return Response({'error': 'Duplicate reference_id'}, status=status.HTTP_409_CONFLICT)
        result = SplitEngine.merchant_split(merchant, ref, amount, data.get('description', ''))
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def charge(self, request, pk=None):
        """
        Initiate M-Pesa STK Push to customer phone.
        Customer sees M-Pesa prompt -> enters PIN -> pays.
        """
        try:
            merchant = Merchant.objects.get(pk=pk)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=status.HTTP_404_NOT_FOUND)

        phone = request.data.get('phone', '').strip()
        amount = Decimal(str(request.data.get('amount', 0)))
        if not phone or amount <= 0:
            return Response({'error': 'phone and amount required'}, status=status.HTTP_400_BAD_REQUEST)

        ref = f"MERCHANT_{merchant.id}"
        result = stk_push(phone, amount, merchant, ref)
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """
        Pay merchant their available balance via M-Pesa B2C.
        """
        try:
            merchant = Merchant.objects.get(pk=pk)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            # Get available balance from ledger
            dash = SplitEngine.merchant_dashboard(merchant)
            amount = Decimal(dash['available'])
            if amount <= 0:
                return Response({'error': 'No balance to withdraw'}, status=status.HTTP_400_BAD_REQUEST)

            # Record the settlement in the ledger first
            ref = _make_ref("STL")
            SplitEngine.merchant_withdraw(merchant, ref)

            # Send real money via M-Pesa B2C
            phone = merchant.phone
            b2c_result = b2c_payment(phone, amount, merchant, ref)

            return Response({
                "settled": str(amount),
                "to_phone": phone,
                "ledger_ref": ref,
                "mpesa_response": b2c_result,
            })
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Account.DoesNotExist:
            return Response({'error': 'No earnings yet. Receive a payment first.'}, status=status.HTTP_400_BAD_REQUEST)
