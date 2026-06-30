from decimal import Decimal
from datetime import datetime, timedelta
from .base import PaymentProvider, CrossDeviceAuthRequest, CrossDeviceAuthResponse


class MockProvider(PaymentProvider):
    """
    Fake provider. Proves the LEDGER works without any internet or real API.
    Simulates all three auth methods.
    """

    name = "mock"
    auth_method = "sim_toolkit"  # Default for behavior parity with M-Pesa

    def initiate_cross_device_auth(self, request: CrossDeviceAuthRequest) -> CrossDeviceAuthResponse:
        return CrossDeviceAuthResponse(
            status="awaiting_user_auth",
            reference=f"MOCK_{request.user_identifier}_{int(request.amount)}",
            our_reference=request.order_reference,
            amount=request.amount,
            currency=request.currency,
            auth_method="sim_toolkit",
            expires_at=datetime.now() + timedelta(minutes=5),
            raw_response={"simulated": True},
        )

    def check_status(self, reference: str) -> dict:
        return {"status": "success", "reference": reference}

    def parse_callback(self, raw_payload: dict) -> dict:
        return {
            "success": True,
            "reference": raw_payload.get("reference", "MOCK_REF"),
            "amount": Decimal(raw_payload.get("amount", 0)),
            "raw": raw_payload,
        }

    def payout(self, amount: Decimal, recipient: str) -> dict:
        return {
            "reference": f"MOCK_PAYOUT_{recipient}_{int(amount)}",
            "status": "sent",
            "provider": "mock",
        }
