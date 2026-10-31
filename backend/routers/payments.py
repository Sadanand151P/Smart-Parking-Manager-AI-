from flask import Blueprint, jsonify, g
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import query
from utils.auth_decorator import login_required

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


@payments_bp.route("/my-payments", methods=["GET"])
@login_required()
def my_payments():
    rows = query(
        """SELECT pay.*, b.booking_ref, p.name as parking_name
           FROM payments pay
           JOIN bookings b ON b.id = pay.booking_id
           JOIN parking_facilities p ON p.id = b.parking_id
           WHERE b.user_id=? ORDER BY pay.created_at DESC""",
        (g.user_id,),
    )
    return jsonify(rows)


@payments_bp.route("/<int:booking_id>", methods=["GET"])
@login_required()
def payment_for_booking(booking_id):
    row = query(
        """SELECT pay.* FROM payments pay
           JOIN bookings b ON b.id = pay.booking_id
           WHERE pay.booking_id=? AND b.user_id=?""",
        (booking_id, g.user_id), fetch="one",
    )
    if not row:
        return jsonify({"error": "no payment found for this booking"}), 404
    return jsonify(row)
