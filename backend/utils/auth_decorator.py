from functools import wraps
from flask import request, jsonify, g
from utils.security import decode_token


def login_required(roles=None):
    """roles: optional list of allowed roles, e.g. ['admin'] or ['owner', 'admin']."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Missing or invalid Authorization header"}), 401
            token = auth_header.split(" ", 1)[1]
            payload = decode_token(token)
            if not payload:
                return jsonify({"error": "Invalid or expired token"}), 401
            if roles and payload.get("role") not in roles:
                return jsonify({"error": "Forbidden — insufficient role"}), 403
            g.user_id = payload["sub"]
            g.user_role = payload["role"]
            return fn(*args, **kwargs)
        return wrapper
    return decorator
