"""
M-Pesa Daraja API adapter.
Wires Safaricom APIs into the SplitEngine ledger.

APIs used:
  - M-Pesa Express (STK Push) — customer pays
  - Business To Customer (B2C) — merchant withdrawal
  - Pull Transactions — end-of-day reconciliation
  - Account Balance — check till float
"""
import base64
import json
import os
from datetime import datetime
from decimal import Decimal

import requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.db import transaction as db_transaction

from .models import Account, Merchant
from .services import SplitEngine


# ──────────────────────────────────────────────
# 1. AUTH — get OAuth token from Safaricom
# ──────────────────────────────────────────────

def get_token():
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    key = settings.MPESA_CONSUMER_KEY
    secret = settings.MPESA_CONSUMER_SECRET
    auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
    resp = requests.get(url, headers={"Authorization": f"Basic {auth}"})
    resp.raise_for_status()
    return resp.json()["access_token"]


# ──────────────────────────────────────────────
# 2. STK PUSH — customer pays via M-Pesa prompt
# ──────────────────────────────────────────────

def stk_push(phone: str, amount: Decimal, merchant: Merchant, reference: str) -> dict:
    """
    Initiate STK Push to customer phone.
    On success, M-Pesa sends callback to /api/webhooks/mpesa/c2b/
    """
    token = get_token()
    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    pwd = base64.b64encode(
        f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{ts}".encode()
    ).decode()

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": pwd,
        "Timestamp": ts,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": str(int(amount)),
        "PartyA": phone,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": f"{settings.BASE_URL}/api/webhooks/mpesa/c2b/",
        "AccountReference": reference,
        "TransactionDesc": f"Payment to {merchant.business_name}",
    }

    resp = requests.post(
        url, json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    data = resp.json()

    if data.get("ResponseCode") == "0":
        return {"status": "pending", "checkout_id": data["CheckoutRequestID"], "reference": reference}
    return {"status": "failed", "error": data.get("errorMessage", "STK push failed")}


# ──────────────────────────────────────────────
# 3. C2B CALLBACK — M-Pesa hits this after customer pays
# ──────────────────────────────────────────────

@csrf_exempt
def c2b_callback(request):
    """
    M-Pesa sends the payment result here.
    We parse the result and record it in the ledger.
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    body = json.loads(request.body)
    stk_callback = body.get("Body", {}).get("stkCallback", {})

    result_code = stk_callback.get("ResultCode")
    checkout_id = stk_callback.get("CheckoutRequestID")
    metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])

    if result_code != 0:
        # Payment failed — nothing to record
        return JsonResponse({"status": "failed", "checkout_id": checkout_id})

    # Extract M-Pesa transaction details
    tx = {item["Name"]: item["Value"] for item in metadata}
    mpesa_ref = tx.get("MpesaReceiptNumber", checkout_id)
    phone = str(tx.get("PhoneNumber", ""))
    amount = Decimal(str(tx.get("Amount", 0))).quantize(Decimal("0.01"))

    # Who does this payment belong to? Stored in AccountReference when we sent STK
    account_ref = stk_callback.get("AccountReference", "")

    # Extract merchant from the account reference format "MERCHANT_{id}"
    try:
        merchant_id = int(account_ref.replace("MERCHANT_", ""))
        merchant = Merchant.objects.get(pk=merchant_id)
    except (ValueError, Merchant.DoesNotExist):
        return JsonResponse({"error": "Unknown merchant"}, status=400)

    # ⚡ THE MAGIC: record in the immutable ledger
    result = SplitEngine.merchant_split(merchant, mpesa_ref, amount,
                                        f"M-Pesa {mpesa_ref} - {merchant.business_name}")

    return JsonResponse({
        "status": "completed",
        "mpesa_ref": mpesa_ref,
        "ledger": result,
    })


# ──────────────────────────────────────────────
# 4. B2C — send money FROM your till TO merchant phone
# ──────────────────────────────────────────────

def b2c_payment(phone: str, amount: Decimal, merchant: Merchant, reference: str) -> dict:
    """
    Pay a merchant from your business account to their personal M-Pesa.
    Called when merchant clicks "Withdraw" on the dashboard.
    """
    token = get_token()
    url = "https://sandbox.safaricom.co.ke/mpesa/b2c/v3/paymentrequest"

    payload = {
        "InitiatorName": settings.MPESA_INITIATOR,
        "SecurityCredential": settings.MPESA_SECURITY_CRED,
        "CommandID": "BusinessPayment",
        "Amount": str(int(amount)),
        "PartyA": settings.MPESA_SHORTCODE,
        "PartyB": phone,
        "Remarks": f"Settlement {reference}",
        "QueueTimeOutURL": f"{settings.BASE_URL}/api/webhooks/mpesa/timeout/",
        "ResultURL": f"{settings.BASE_URL}/api/webhooks/mpesa/b2c/",
        "Occasion": merchant.business_name,
    }

    resp = requests.post(
        url, json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    return resp.json()


@csrf_exempt
def b2c_callback(request):
    """M-Pesa tells us the B2C result."""
    if request.method != "POST":
        return HttpResponse(status=405)
    # In production, parse result and update settlement status
    return JsonResponse({"status": "processing"})


@csrf_exempt
def timeout_callback(request):
    """M-Pesa couldn't process in time."""
    return JsonResponse({"status": "timeout"})


# ──────────────────────────────────────────────
# 5. RECONCILIATION — pull transactions from Safaricom
# ──────────────────────────────────────────────

def pull_transactions(shortcode: str, date: str = None) -> list:
    """
    Pull all C2B transactions for a given date.
    Compare with your ledger to verify accuracy.
    """
    token = get_token()
    url = "https://sandbox.safaricom.co.ke/mpesa/transactionstatus/v1/query"

    payload = {
        "Initiator": settings.MPESA_INITIATOR,
        "SecurityCredential": settings.MPESA_SECURITY_CRED,
        "CommandID": "TransactionStatusQuery",
        "TransactionID": "",
        "PartyA": shortcode,
        "IdentifierType": "4",
        "ResultURL": f"{settings.BASE_URL}/api/webhooks/mpesa/reconcile/",
        "QueueTimeOutURL": f"{settings.BASE_URL}/api/webhooks/mpesa/timeout/",
        "Remarks": "Reconciliation",
        "Occasion": "Daily pull",
    }
    resp = requests.post(
        url, json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    return resp.json()
