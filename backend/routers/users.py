from flask import Blueprint, request, jsonify, g
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import query
from utils.auth_decorator import login_required
from utils.validation import sanitize_str, is_valid_email
from utils.security import verify_password, hash_password

users_bp = Blueprint("users", __name__, url_prefix="/api/users")


@users_bp.route("/me", methods=["GET"])
@login_required()
def get_profile():
    user = query("SELECT id, name, email, mobile, role, is_verified, created_at FROM users WHERE id=?",
                 (g.user_id,), fetch="one")
    if not user:
        return jsonify({"error": "user not found"}), 404
    return jsonify(user)


@users_bp.route("/me", methods=["PUT"])
@login_required()
def update_profile():
    data = request.get_json(force=True)
    name = sanitize_str(data.get("name")) if "name" in data else None
    email = sanitize_str(data.get("email")).lower() if "email" in data else None

    if email and not is_valid_email(email):
        return jsonify({"error": "invalid email"}), 400

    fields, params = [], []
    if name:
        fields.append("name=?"); params.append(name)
    if email:
        fields.append("email=?"); params.append(email)
    if not fields:
        return jsonify({"error": "nothing to update"}), 400

    params.append(g.user_id)
    query(f"UPDATE users SET {', '.join(fields)} WHERE id=?", tuple(params))
    return jsonify({"message": "profile updated"})


@users_bp.route("/me/change-password", methods=["POST"])
@login_required()
def change_password():
    data = request.get_json(force=True)
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")

    user = query("SELECT password_hash FROM users WHERE id=?", (g.user_id,), fetch="one")
    if not verify_password(old_password, user["password_hash"]):
        return jsonify({"error": "old password is incorrect"}), 401
    if len(new_password) < 6:
        return jsonify({"error": "new password must be at least 6 characters"}), 400

    query("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_password), g.user_id))
    return jsonify({"message": "password changed"})


@users_bp.route("/me/bookings", methods=["GET"])
@login_required()
def my_bookings():
    rows = query(
        """SELECT b.*, p.name as parking_name, p.address, v.vehicle_number
           FROM bookings b
           JOIN parking_facilities p ON p.id = b.parking_id
           JOIN vehicles v ON v.id = b.vehicle_id
           WHERE b.user_id=? ORDER BY b.created_at DESC""",
        (g.user_id,),
    )
    return jsonify(rows)
