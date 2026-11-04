from flask import Blueprint, request, jsonify  # type: ignore[reportMissingImports]
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import query
from utils.security import hash_password, verify_password, create_token
from utils.validation import is_valid_mobile, is_valid_email, sanitize_str
from services.sms_service import send_otp, verify_otp

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    name = sanitize_str(data.get("name"))
    email = sanitize_str(data.get("email")).lower()
    mobile = sanitize_str(data.get("mobile"))
    password = data.get("password", "")
    role = data.get("role", "customer")

    if not name or not password:
        return jsonify({"error": "name and password are required"}), 400
    if not is_valid_email(email):
        return jsonify({"error": "invalid email"}), 400
    if not is_valid_mobile(mobile):
        return jsonify({"error": "invalid Indian mobile number"}), 400
    if role not in ("customer", "owner"):
        return jsonify({"error": "role must be customer or owner"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    existing = query("SELECT id FROM users WHERE email=? OR mobile=?", (email, mobile), fetch="one")
    if existing:
        return jsonify({"error": "an account with this email or mobile already exists"}), 409

    user_id = query(
        "INSERT INTO users (name, email, mobile, password_hash, role) VALUES (?, ?, ?, ?, ?)",
        (name, email, mobile, hash_password(password), role),
    )
    otp_result = send_otp(mobile, purpose="register")
    resp = {"message": "registered — OTP sent for verification", "user_id": user_id}
    if "debug_otp" in otp_result:
        resp["debug_otp"] = otp_result["debug_otp"]  # only present in mock/dev mode
    return jsonify(resp), 201


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_registration_otp():
    data = request.get_json(force=True)
    mobile = sanitize_str(data.get("mobile"))
    code = sanitize_str(data.get("otp"))
    purpose = data.get("purpose", "register")

    if not verify_otp(mobile, code, purpose):
        return jsonify({"error": "invalid or expired OTP"}), 400

    query("UPDATE users SET is_verified=1 WHERE mobile=?", (mobile,))
    user = query("SELECT id, role FROM users WHERE mobile=?", (mobile,), fetch="one")
    token = create_token(user["id"], user["role"])
    return jsonify({"message": "mobile verified", "token": token})


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    identifier = sanitize_str(data.get("email_or_mobile")).lower()
    password = data.get("password", "")

    user = query(
        "SELECT * FROM users WHERE email=? OR mobile=?", (identifier, identifier), fetch="one"
    )
    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "invalid credentials"}), 401
    if not user["is_verified"]:
        return jsonify({"error": "account not verified — complete OTP verification first"}), 403

    token = create_token(user["id"], user["role"])
    return jsonify({
        "token": token,
        "user": {"id": user["id"], "name": user["name"], "email": user["email"],
                  "mobile": user["mobile"], "role": user["role"]},
    })


@auth_bp.route("/forgot-password/request-otp", methods=["POST"])
def forgot_password_request():
    data = request.get_json(force=True)
    mobile = sanitize_str(data.get("mobile"))
    user = query("SELECT id FROM users WHERE mobile=?", (mobile,), fetch="one")
    if not user:
        return jsonify({"error": "no account with this mobile number"}), 404
    otp_result = send_otp(mobile, purpose="reset")
    resp = {"message": "OTP sent for password reset"}
    if "debug_otp" in otp_result:
        resp["debug_otp"] = otp_result["debug_otp"]
    return jsonify(resp)


@auth_bp.route("/forgot-password/reset", methods=["POST"])
def forgot_password_reset():
    data = request.get_json(force=True)
    mobile = sanitize_str(data.get("mobile"))
    code = sanitize_str(data.get("otp"))
    new_password = data.get("new_password", "")

    if not verify_otp(mobile, code, "reset"):
        return jsonify({"error": "invalid or expired OTP"}), 400
    if len(new_password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    query("UPDATE users SET password_hash=? WHERE mobile=?", (hash_password(new_password), mobile))
    return jsonify({"message": "password reset successful"})
