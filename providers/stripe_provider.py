"""
Stripe Payment Intents provider — proves the abstraction works across geographies.
Uses the same initiate_cross_device_auth pattern as M-Pesa, but Stripe
returns a client_secret that must be confirmed by the buyer's browser.
"""
from datetime import datetime, timedelta
from decimal import Decimal
import os

from .base import PaymentProvider, CrossDeviceAuthRequest, CrossDeviceAuthResponse


class StripeProvider(PaymentProvider):
    name = "stripe"
    auth_method = "native_ui"

    def initiate_cross_device_auth(self, request: CrossDeviceAuthRequest) -> CrossDeviceAuthResponse:
        """
        In production this would call stripe.PaymentIntent.create().
        The returned client_secret is the redirect_url for the frontend.
        """
        secret_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_local")
        return CrossDeviceAuthResponse(
            status="awaiting_user_auth",
            reference=f"pi_mock_{int(request.amount)}_{request.user_identifier[-4:]}",
            our_reference=request.order_reference,
            amount=request.amount,
            currency=request.currency,
            auth_method="native_ui",
            redirect_url=f"https://checkout.stripe.com/c/pay/mock_client_secret",
            expires_at=datetime.now() + timedelta(hours=1),
            raw_response={"requires_confirmation": True},
        )

    def check_status(self, reference: str) -> dict:
        return {"status": "requires_confirmation", "reference": reference}

    def parse_callback(self, raw_payload: dict) -> dict:
        event_type = raw_payload.get("type", "")
        pi = raw_payload.get("data", {}).get("object", {})
        return {
            "success": event_type == "payment_intent.succeeded",
            "reference": pi.get("id", ""),
            "amount": Decimal(str(pi.get("amount", 0))) / 100,
            "currency": pi.get("currency", "usd").upper(),
            "our_reference": pi.get("metadata", {}).get("order_reference", ""),
            "raw": raw_payload,
        }

    def payout(self, amount: Decimal, recipient: str) -> dict:
        return {
            "reference": f"po_mock_{recipient[-4:]}_{int(amount)}",
            "status": "sent",
            "provider": "stripe",
        }
