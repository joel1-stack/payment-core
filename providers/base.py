from abc import ABC, abstractmethod
from decimal import Decimal


class PaymentProvider(ABC):
    """Abstract payment provider. Every rail (M-Pesa, Stripe, Mock) implements this."""

    @abstractmethod
    def charge(self, amount: Decimal, currency: str, customer_ref: str) -> dict:
        """Initiate a customer payment. Returns {'reference': str, 'status': str}"""

    @abstractmethod
    def verify(self, reference: str) -> dict:
        """Check if a transaction was completed."""

    @abstractmethod
    def payout(self, amount: Decimal, recipient: str) -> dict:
        """Send money to a merchant/recipient. Returns {'reference': str, 'status': str}"""
