from abc import ABC, abstractmethod
from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class CrossDeviceAuthRequest:
    amount: Decimal
    currency: str
    user_identifier: str
    merchant_id: str
    order_reference: str
    callback_url: str
    metadata: dict = field(default_factory=dict)


@dataclass
class CrossDeviceAuthResponse:
    status: str                         # "awaiting_user_auth" | "failed" | "instant_success"
    reference: str                      # Provider's transaction reference
    our_reference: str                  # Your order_reference (for idempotency)
    amount: Decimal
    currency: str
    auth_method: str                    # "sim_toolkit" | "deep_link" | "native_ui"
    redirect_url: Optional[str] = None  # For UPI/Stripe (user must visit)
    expires_at: Optional[datetime] = None
    raw_response: dict = field(default_factory=dict)


class PaymentProvider(ABC):
    """
    Every payment rail on earth implements this.
    The ledger calls this. The ledger doesn't know M-Pesa from Stripe.
    """

    name: str = "base"
    auth_method: str = "unknown"

    @abstractmethod
    def initiate_cross_device_auth(self, request: CrossDeviceAuthRequest) -> CrossDeviceAuthResponse:
        """
        Step 1: Ping the user's secondary device for approval.
        Returns immediately. Money has NOT moved yet.
        """

    @abstractmethod
    def check_status(self, reference: str) -> dict:
        """Step 2: Poll or verify the transaction status."""

    @abstractmethod
    def parse_callback(self, raw_payload: dict) -> dict:
        """
        Step 3: Normalize provider-specific webhook into universal format.
        Returns: {"success": bool, "reference": str, "amount": Decimal, ...}
        """

    def charge(self, amount: Decimal, currency: str, customer_ref: str) -> dict:
        """Legacy: simpler interface for non-cross-device flows."""
        req = CrossDeviceAuthRequest(
            amount=amount,
            currency=currency,
            user_identifier=customer_ref,
            merchant_id="",
            order_reference=f"CHG_{customer_ref}_{int(amount)}",
            callback_url="",
        )
        resp = self.initiate_cross_device_auth(req)
        return {
            "reference": resp.reference,
            "status": resp.status,
            "provider": self.name,
        }

    def verify(self, reference: str) -> dict:
        return self.check_status(reference)

    def payout(self, amount: Decimal, recipient: str) -> dict:
        """Override in providers that support disbursements (M-Pesa B2C, Stripe Payouts)."""
        return {"reference": f"PAYOUT_{recipient}", "status": "sent", "provider": self.name}
