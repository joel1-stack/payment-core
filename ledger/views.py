from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Account, Transaction, JournalEntry
from .serializers import AccountSerializer, TransactionSerializer, JournalEntrySerializer
from .services import SplitEngine, SplitRule


class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer


class JournalEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JournalEntry.objects.all()
    serializer_class = JournalEntrySerializer


class PaymentSplitViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'])
    def split(self, request):
        data = request.data
        total_amount = Decimal(str(data.get('amount', 0)))
        reference_id = data.get('reference_id')
        pool_account = data.get('pool_account', 'M-Pesa Pool Account')
        rules_data = data.get('rules', [])

        if not reference_id:
            return Response({'error': 'reference_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        if Transaction.objects.filter(reference_id=reference_id).exists():
            return Response({'error': 'Transaction already exists'}, status=status.HTTP_409_CONFLICT)

        if not rules_data:
            return Response({'error': 'At least one split rule is required'}, status=status.HTTP_400_BAD_REQUEST)

        split_rules = [
            SplitRule(r['account_name'], Decimal(str(r['percentage'])), r.get('account_type', 'LIABILITY'))
            for r in rules_data
        ]

        engine = SplitEngine()
        result = engine.execute_payment_split(
            reference_id=reference_id,
            total_amount=total_amount,
            pool_account_name=pool_account,
            split_rules=split_rules,
            description=data.get('description', ''),
        )

        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def refund(self, request):
        data = request.data
        original_ref = data.get('original_reference_id')
        refund_ref = data.get('refund_reference_id')

        if not original_ref or not refund_ref:
            return Response({'error': 'original_reference_id and refund_reference_id are required'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            engine = SplitEngine()
            result = engine.execute_refund(
                original_reference_id=original_ref,
                refund_reference_id=refund_ref,
                description=data.get('description', ''),
            )
            return Response(result, status=status.HTTP_201_CREATED)
        except Transaction.DoesNotExist:
            return Response({'error': 'Original transaction not found'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
