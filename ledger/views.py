from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Account, Transaction, JournalEntry, Merchant
from .serializers import AccountSerializer, TransactionSerializer, JournalEntrySerializer
from .services import SplitEngine


class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer


class JournalEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JournalEntry.objects.all()
    serializer_class = JournalEntrySerializer


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
    def withdraw(self, request, pk=None):
        try:
            merchant = Merchant.objects.get(pk=pk)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=status.HTTP_404_NOT_FOUND)
        ref = request.data.get('reference_id', f"STL_{merchant.id}_{Transaction.objects.count() + 1}")
        try:
            result = SplitEngine.merchant_withdraw(merchant, ref)
            return Response(result)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Account.DoesNotExist:
            return Response({'error': 'No earnings account found. Receive a payment first.'}, status=status.HTTP_400_BAD_REQUEST)
