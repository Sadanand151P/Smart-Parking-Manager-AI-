import datetime
import random
import string
from flask import Blueprint, request, jsonify, g
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import get_db, query
from utils.auth_decorator import login_required
from services.qr_service import build_qr_payload, render_qr_placeholder
from services.sms_service import send_sms
from services.payment_service import charge

bookings_bp = Blueprint("bookings", __name__, url_prefix="/api/bookings")


def _booking_ref() -> str:
    today = datetime.date.today().strftime("%Y%m%d")
    suffix = "".join(random.choices(string.digits, k=5))
    return f"SPK-{today}-{suffix}"


@bookings_bp.route("", methods=["POST"])
@login_required()
def create_booking():
    """
    Creates a reservation with slot locking: we hold the DB connection through
    the free-slot check + reservation UPDATE so two simultaneous requests
    can't both grab the same slot (classic double-booking race condition).
    """
    d = request.get_json(force=True)
    parking_id = d.get("parking_id")
    vehicle_id = d.get("vehicle_id")
    booking_date = d.get("booking_date")   # YYYY-MM-DD
    start_time = d.get("start_time")       # HH:MM
    end_time = d.get("end_time")           # HH:MM

    if not all([parking_id, vehicle_id, booking_date, start_time, end_time]):
        return jsonify({"error": "parking_id, vehicle_id, booking_date, start_time, end_time are required"}), 400

    vehicle = query("SELECT * FROM vehicles WHERE id=? AND user_id=?", (vehicle_id, g.user_id), fetch="one")
    if not vehicle:
        return jsonify({"error": "vehicle not found or not yours"}), 404

    facility = query("SELECT * FROM parking_facilities WHERE id=? AND status='approved'",
                     (parking_id,), fetch="one")
    if not facility:
        return jsonify({"error": "parking facility not found or not approved"}), 404

    vehicle_type_for_slot = "4-wheeler" if vehicle["vehicle_type"] in ("4-wheeler", "ev") else "2-wheeler"
    price_per_hour = facility["price_4w"] if vehicle_type_for_slot == "4-wheeler" else facility["price_2w"]

    try:
        t1 = datetime.datetime.strptime(start_time, "%H:%M")
        t2 = datetime.datetime.strptime(end_time, "%H:%M")
        hours = max(1.0, (t2 - t1).seconds / 3600)
    except ValueError:
        return jsonify({"error": "start_time/end_time must be HH:MM"}), 400

    amount = round(price_per_hour * hours, 2)

    # --- slot lock: single transaction, pick + reserve atomically ---
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        slot = conn.execute(
            "SELECT id, slot_number FROM parking_slots WHERE parking_id=? AND vehicle_type=? AND status='free' LIMIT 1",
            (parking_id, vehicle_type_for_slot),
        ).fetchone()
        if not slot:
            conn.rollback()
            conn.close()
            return jsonify({"error": "no free slots for this vehicle type", "suggest_alternative": True}), 409

        booking_ref = _booking_ref()
        conn.execute("UPDATE parking_slots SET status='reserved' WHERE id=?", (slot["id"],))
        cur = conn.execute(
            """INSERT INTO bookings
               (booking_ref, user_id, parking_id, slot_id, vehicle_id, booking_date,
                start_time, end_time, booking_status, amount)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (booking_ref, g.user_id, parking_id, slot["id"], vehicle_id, booking_date,
             start_time, end_time, "confirmed", amount),
        )
        booking_id = cur.lastrowid

        payload = build_qr_payload(booking_ref, vehicle["vehicle_number"], facility["name"],
                                   slot["slot_number"], f"{booking_date} {start_time}", f"{booking_date} {end_time}")
        conn.execute("UPDATE bookings SET qr_payload=? WHERE id=?", (payload, booking_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": f"booking failed: {e}"}), 500
    conn.close()

    qr_path = render_qr_placeholder(payload, booking_ref)

    user = query("SELECT mobile FROM users WHERE id=?", (g.user_id,), fetch="one")
    message = (
        f"SmartPark India\n\nBooking Confirmed!\n\nParking: {facility['name']}\n"
        f"Booking ID: {booking_ref}\nVehicle: {vehicle['vehicle_number']}\n"
        f"Date: {booking_date}\nTime: {start_time}\nSlot: {slot['slot_number']}\n\n"
        f"Please arrive 10 minutes early."
    )
    send_sms(user["mobile"], message)
    query(
        "INSERT INTO notifications (user_id, booking_id, type, message) VALUES (?,?,?,?)",
        (g.user_id, booking_id, "confirmation", message),
    )

    return jsonify({
        "message": "booking confirmed",
        "booking_id": booking_id,
        "booking_ref": booking_ref,
        "slot_number": slot["slot_number"],
        "amount": amount,
        "qr_ticket_path": qr_path,
    }), 201


@bookings_bp.route("/<int:booking_id>/pay", methods=["POST"])
@login_required()
def pay_booking(booking_id):
    booking = query("SELECT * FROM bookings WHERE id=? AND user_id=?", (booking_id, g.user_id), fetch="one")
    if not booking:
        return jsonify({"error": "booking not found"}), 404
    d = request.get_json(force=True)
    method = d.get("payment_method", "upi")
    result = charge(booking_id, booking["amount"], method)
    return jsonify(result)


@bookings_bp.route("/<int:booking_id>/cancel", methods=["POST"])
@login_required()
def cancel_booking(booking_id):
    booking = query("SELECT * FROM bookings WHERE id=? AND user_id=?", (booking_id, g.user_id), fetch="one")
    if not booking:
        return jsonify({"error": "booking not found"}), 404
    if booking["booking_status"] != "confirmed":
        return jsonify({"error": f"cannot cancel a booking with status '{booking['booking_status']}'"}), 400

    query("UPDATE bookings SET booking_status='cancelled' WHERE id=?", (booking_id,))
    if booking["slot_id"]:
        query("UPDATE parking_slots SET status='free' WHERE id=?", (booking["slot_id"],))

    user = query("SELECT mobile FROM users WHERE id=?", (g.user_id,), fetch="one")
    message = f"Your booking {booking['booking_ref']} has been cancelled successfully."
    send_sms(user["mobile"], message)
    query("INSERT INTO notifications (user_id, booking_id, type, message) VALUES (?,?,?,?)",
          (g.user_id, booking_id, "cancellation", message))

    return jsonify({"message": "booking cancelled"})


@bookings_bp.route("/<int:booking_id>", methods=["GET"])
@login_required()
def booking_details(booking_id):
    booking = query(
        """SELECT b.*, p.name as parking_name, p.address, v.vehicle_number
           FROM bookings b
           JOIN parking_facilities p ON p.id = b.parking_id
           JOIN vehicles v ON v.id = b.vehicle_id
           WHERE b.id=? AND b.user_id=?""",
        (booking_id, g.user_id), fetch="one",
    )
    if not booking:
        return jsonify({"error": "booking not found"}), 404
    return jsonify(booking)


@bookings_bp.route("/<int:booking_id>/review", methods=["POST"])
@login_required()
def review_booking(booking_id):
    booking = query("SELECT * FROM bookings WHERE id=? AND user_id=?", (booking_id, g.user_id), fetch="one")
    if not booking:
        return jsonify({"error": "booking not found"}), 404
    d = request.get_json(force=True)
    rating = int(d.get("rating", 0))
    comment = d.get("comment", "")
    if not (1 <= rating <= 5):
        return jsonify({"error": "rating must be 1-5"}), 400

    query("INSERT INTO reviews (booking_id, parking_id, user_id, rating, comment) VALUES (?,?,?,?,?)",
          (booking_id, booking["parking_id"], g.user_id, rating, comment))

    agg = query(
        "SELECT AVG(rating) as avg_rating, COUNT(*) as cnt FROM reviews WHERE parking_id=?",
        (booking["parking_id"],), fetch="one",
    )
    query("UPDATE parking_facilities SET rating=?, rating_count=? WHERE id=?",
          (round(agg["avg_rating"], 2), agg["cnt"], booking["parking_id"]))

    return jsonify({"message": "review submitted"})
