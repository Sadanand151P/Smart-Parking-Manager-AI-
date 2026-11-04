"""
SMS / OTP service.

Wraps an MSG91-shaped interface (send_otp / verify_otp / send_sms) behind a
provider abstraction. In this dev build MSG91_AUTH_KEY is absent, so calls
fall back to a console/DB "mock" provider — the OTP is written to the
otp_codes table and printed, instead of actually hitting MSG91's API. Swap
USE_MOCK to False and set MSG91_AUTH_KEY in .env to go live; the calling
code (routers/auth.py) does not change either way.
"""

import os
import random
import string
import datetime
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import query

MSG91_AUTH_KEY = os.environ.get("SMS_AUTH_KEY", "")
USE_MOCK = not bool(MSG91_AUTH_KEY)
OTP_VALIDITY_MINUTES = 5


def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def send_otp(mobile: str, purpose: str = "login") -> dict:
    code = _generate_otp()
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(minutes=OTP_VALIDITY_MINUTES)).isoformat()
    query(
        "INSERT INTO otp_codes (mobile, code, purpose, expires_at) VALUES (?, ?, ?, ?)",
        (mobile, code, purpose, expires_at),
    )
    if USE_MOCK:
        print(f"[sms_service:MOCK] OTP for +91{mobile} ({purpose}): {code} (valid {OTP_VALIDITY_MINUTES} min)")
        return {"status": "sent", "provider": "mock", "debug_otp": code}
    else:
        # Real MSG91 call would go here, e.g.:
        # requests.post("https://control.msg91.com/api/v5/otp", ...)
        raise NotImplementedError("Set SMS_AUTH_KEY and implement the live MSG91 call in production.")


def verify_otp(mobile: str, code: str, purpose: str = "login") -> bool:
    row = query(
        """SELECT id, expires_at FROM otp_codes WHERE mobile=? AND code=? AND purpose=? AND is_used=0
           ORDER BY id DESC LIMIT 1""",
        (mobile, code, purpose),
        fetch="one",
    )
    if not row:
        return False

    if isinstance(row, dict):
        otp_id = row.get("id")
        expires_at = row.get("expires_at")
    elif isinstance(row, (list, tuple)) and len(row) >= 2:
        otp_id = row[0]
        expires_at = row[1]
    else:
        return False

    if expires_at is None or not isinstance(expires_at, str):
        return False

    if datetime.datetime.fromisoformat(expires_at) < datetime.datetime.utcnow():
        return False
    query("UPDATE otp_codes SET is_used=1 WHERE id=?", (otp_id,))
    return True


def send_sms(mobile: str, message: str) -> dict:
    if USE_MOCK:
        print(f"[sms_service:MOCK] SMS to +91{mobile}:\n{message}\n")
        return {"status": "sent", "provider": "mock"}
    raise NotImplementedError("Set SMS_AUTH_KEY and implement the live MSG91 call in production.")
