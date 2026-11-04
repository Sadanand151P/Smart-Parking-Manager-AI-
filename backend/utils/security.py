"""
Password hashing (PBKDF2, stdlib-only — no bcrypt/passlib available in this
sandbox, but PBKDF2-HMAC-SHA256 with a per-password salt is a solid,
dependency-free choice) and JWT issuing/verification via PyJWT.
"""

import hashlib
import hmac
import os
import base64
import time
import jwt

SECRET_KEY = os.environ.get("JWT_SECRET", "dev-secret-change-me-in-.env")
JWT_ALGO = "HS256"
JWT_EXPIRY_SECONDS = 60 * 60 * 24 * 7  # 7 days
PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_b64, dk_b64 = stored_hash.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
        return hmac.compare_digest(expected, actual)
    except Exception:
        return False


def create_token(user_id: int, role: str) -> str:
    payload = {"sub": user_id, "role": role, "exp": int(time.time()) + JWT_EXPIRY_SECONDS}
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGO)


def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        return None
