"""
M-Pesa Daraja provider — inherits from PaymentProvider.
Implements initiate_cross_device_auth using STK Push (SIM Toolkit).
"""
import base64
from datetime import datetime, timedelta
from decimal import Decimal

import requests
from django.conf import settings

from .base import PaymentProvider, CrossDeviceAuthRequest, CrossDeviceAuthResponse


class MpesaProvider(PaymentProvider):
    name = "mpesa"
    auth_method = "sim_toolkit"

    def __init__(self, **kwargs):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.passkey = settings.MPESA_PASSKEY
        self.shortcode = settings.MPESA_SHORTCODE
        self.initiator = settings.MPESA_INITIATOR
        self.initiator_pass = settings.MPESA_INITIATOR_PASS
        self.base_url = "https://sandbox.safaricom.co.ke"
        self.callback_base = settings.BASE_URL

    def _get_token(self) -> str:
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        auth = base64.b64encode(f"{self.consumer_key}:{self.consumer_secret}".encode()).decode()
        resp = requests.get(url, headers={"Authorization": f"Basic {auth}"})
        resp.raise_for_status()
        return resp.json()["access_token"]

    def initiate_cross_device_auth(self, request: CrossDeviceAuthRequest) -> CrossDeviceAuthResponse:
        token = self._get_token()
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        pwd = base64.b64encode(f"{self.shortcode}{self.passkey}{ts}".encode()).decode()

        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": pwd,
            "Timestamp": ts,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(request.amount),
            "PartyA": request.user_identifier,
            "PartyB": self.shortcode,
            "PhoneNumber": request.user_identifier,
            "CallBackURL": request.callback_url or f"{self.callback_base}/api/webhooks/mpesa/c2b/",
            "AccountReference": request.order_reference,
            "TransactionDesc": f"Payment {request.order_reference}",
        }

        resp = requests.post(
            f"{self.base_url}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()

        if data.get("ResponseCode") != "0":
            return CrossDeviceAuthResponse(
                status="failed",
                reference="",
                our_reference=request.order_reference,
                amount=request.amount,
                currency=request.currency,
                auth_method="sim_toolkit",
                raw_response=data,
            )

        return CrossDeviceAuthResponse(
            status="awaiting_user_auth",
            reference=data["CheckoutRequestID"],
            our_reference=request.order_reference,
            amount=request.amount,
            currency=request.currency,
            auth_method="sim_toolkit",
            expires_at=datetime.now() + timedelta(minutes=5),
            raw_response=data,
        )

    def check_status(self, reference: str) -> dict:
        return {"status": "unknown", "reference": reference}

    def parse_callback(self, raw_payload: dict) -> dict:
        """Flatten M-Pesa's deeply nested JSON into universal format."""
        callback = raw_payload.get("Body", {}).get("stkCallback", {})
        result_code = callback.get("ResultCode")
        metadata = callback.get("CallbackMetadata", {}).get("Item", [])

        tx = {item["Name"]: item["Value"] for item in metadata}

        return {
            "success": result_code == 0,
            "reference": callback.get("CheckoutRequestID", ""),
            "amount": Decimal(str(tx.get("Amount", 0))),
            "phone": str(tx.get("PhoneNumber", "")),
            "transaction_id": str(tx.get("MpesaReceiptNumber", "")),
            "our_reference": callback.get("AccountReference", ""),
            "raw": callback,
        }

    def payout(self, amount: Decimal, recipient: str) -> dict:
        """M-Pesa B2C — send money from your till to merchant phone."""
        token = self._get_token()
        url = f"{self.base_url}/mpesa/b2c/v3/paymentrequest"

        ref = f"B2C_{recipient[-4:]}_{int(amount)}"
        payload = {
            "InitiatorName": self.initiator,
            "SecurityCredential": self.initiator_pass,
            "CommandID": "BusinessPayment",
            "Amount": int(amount),
            "PartyA": self.shortcode,
            "PartyB": recipient,
            "Remarks": f"Settlement {ref}",
            "QueueTimeOutURL": f"{self.callback_base}/api/webhooks/mpesa/timeout/",
            "ResultURL": f"{self.callback_base}/api/webhooks/mpesa/b2c/",
            "Occasion": "Withdrawal",
        }

        resp = requests.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
        return resp.json()
