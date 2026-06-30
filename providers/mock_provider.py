from decimal import Decimal
from .base import PaymentProvider


class MockProvider(PaymentProvider):
    """
    Fake provider. Proves the LEDGER works without any internet or real API.

    Use this to demo the engine: no M-Pesa keys, no Stripe account, no internet.
    """

    def charge(self, amount: Decimal, currency: str, customer_ref: str) -> dict:
        return {
            "reference": f"MOCK_{customer_ref}_{int(amount)}",
            "status": "success",
            "provider": "mock",
        }

    def verify(self, reference: str) -> dict:
        return {"status": "success", "reference": reference}

    def payout(self, amount: Decimal, recipient: str) -> dict:
        return {
            "reference": f"MOCK_PAYOUT_{recipient}_{int(amount)}",
            "status": "sent",
            "provider": "mock",
        }
