"""
Payment service.

Mock gateway for the college build: creates a payment row, "succeeds"
deterministically, and returns a transaction id. In production, swap
`charge()` to call Razorpay/Stripe/PayU's server-side order+capture APIs and
verify their webhook signature before marking payment_status='success' —
never trust a client-reported success.
"""

import os
import random
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import query

PAYMENT_SECRET = os.environ.get("PAYMENT_SECRET", "")
USE_MOCK = not bool(PAYMENT_SECRET)


def _txn_id() -> str:
    return "TXN" + "".join(random.choices(string.ascii_uppercase + string.digits, k=12))


def charge(booking_id: int, amount: float, method: str) -> dict:
    if method not in ("upi", "card", "netbanking", "cash"):
        return {"status": "failed", "reason": "invalid_method"}

    txn_id = _txn_id()
    status = "success" if method == "cash" or USE_MOCK else "pending"
    query(
        """INSERT INTO payments (booking_id, transaction_id, amount, payment_method, payment_status)
           VALUES (?, ?, ?, ?, ?)""",
        (booking_id, txn_id, amount, method, status),
    )
    return {"status": status, "transaction_id": txn_id, "amount": amount, "method": method}


def refund(transaction_id: str) -> dict:
    query("UPDATE payments SET payment_status='refunded' WHERE transaction_id=?", (transaction_id,))
    return {"status": "refunded", "transaction_id": transaction_id}
