import datetime
from flask import Blueprint, request, jsonify, g
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import query
from utils.auth_decorator import login_required
from utils.validation import sanitize_str, is_valid_pincode
from services.map_service import nearby_parking, geocode
from services.recommendation_service import recommend

parking_bp = Blueprint("parking", __name__, url_prefix="/api/parking")


def _current_availability(parking_id: int) -> dict:
    row = query(
        """SELECT
             SUM(CASE WHEN vehicle_type='2-wheeler' THEN 1 ELSE 0 END) as cap_2w,
             SUM(CASE WHEN vehicle_type='4-wheeler' THEN 1 ELSE 0 END) as cap_4w,
             SUM(CASE WHEN status='free' THEN 1 ELSE 0 END) as free_total,
             COUNT(*) as total
           FROM parking_slots WHERE parking_id=?""",
        (parking_id,), fetch="one",
    )
    return row or {"free_total": 0, "total": 0}


# ---------------------------------------------------------------- Owner: register a facility

@parking_bp.route("/register", methods=["POST"])
@login_required(roles=["owner", "admin"])
def register_facility():
    d = request.get_json(force=True)
    required = ["name", "address", "city", "state", "latitude", "longitude",
                "capacity_2w", "capacity_4w", "price_2w", "price_4w"]
    missing = [f for f in required if d.get(f) in (None, "")]
    if missing:
        return jsonify({"error": f"missing fields: {', '.join(missing)}"}), 400
    if d.get("pincode") and not is_valid_pincode(str(d["pincode"])):
        return jsonify({"error": "invalid pincode"}), 400

    facility_id = query(
        """INSERT INTO parking_facilities
           (owner_id, name, address, city, state, pincode, latitude, longitude,
            capacity_2w, capacity_4w, price_2w, price_4w, ev_charging, cctv,
            covered, security_guard, opening_time, closing_time, is_24x7, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (g.user_id, sanitize_str(d["name"]), sanitize_str(d["address"]), sanitize_str(d["city"]),
         sanitize_str(d["state"]), sanitize_str(d.get("pincode", "")), float(d["latitude"]), float(d["longitude"]),
         int(d["capacity_2w"]), int(d["capacity_4w"]), float(d["price_2w"]), float(d["price_4w"]),
         int(bool(d.get("ev_charging"))), int(bool(d.get("cctv"))), int(bool(d.get("covered"))),
         int(bool(d.get("security_guard"))), d.get("opening_time", "00:00"), d.get("closing_time", "23:59"),
         int(bool(d.get("is_24x7"))), "pending"),
    )

    # Auto-generate slot rows for 2W/4W capacity
    for i in range(1, int(d["capacity_2w"]) + 1):
        query("INSERT INTO parking_slots (parking_id, slot_number, vehicle_type) VALUES (?,?,?)",
              (facility_id, f"2W-{i:03d}", "2-wheeler"))
    for i in range(1, int(d["capacity_4w"]) + 1):
        query("INSERT INTO parking_slots (parking_id, slot_number, vehicle_type) VALUES (?,?,?)",
              (facility_id, f"4W-{i:03d}", "4-wheeler"))

    return jsonify({"message": "facility submitted for admin approval", "facility_id": facility_id}), 201


@parking_bp.route("/owner/my-facilities", methods=["GET"])
@login_required(roles=["owner", "admin"])
def my_facilities():
    rows = query("SELECT * FROM parking_facilities WHERE owner_id=? ORDER BY created_at DESC", (g.user_id,))
    for r in rows:
        avail = _current_availability(r["id"])
        r["available_slots"] = avail["free_total"]
        r["total_slots"] = avail["total"]
    return jsonify(rows)


@parking_bp.route("/owner/<int:facility_id>/occupancy", methods=["POST"])
@login_required(roles=["owner", "admin"])
def update_occupancy(facility_id):
    """Owner/admin manually updates live occupancy (stand-in for IoT sensors)."""
    owned = query("SELECT id FROM parking_facilities WHERE id=? AND owner_id=?",
                 (facility_id, g.user_id), fetch="one")
    if not owned and g.user_role != "admin":
        return jsonify({"error": "not your facility"}), 403

    d = request.get_json(force=True)
    occupied = int(d.get("occupied", 0))
    avail = _current_availability(facility_id)
    total = avail["total"] or 1
    available = max(0, total - occupied)
    query("INSERT INTO parking_occupancy (parking_id, occupied, available) VALUES (?,?,?)",
          (facility_id, occupied, available))
    return jsonify({"message": "occupancy recorded", "occupied": occupied, "available": available})


# ---------------------------------------------------------------- Public: search & discovery

@parking_bp.route("/nearby", methods=["GET"])
def find_nearby():
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    radius = request.args.get("radius_km", default=5.0, type=float)
    vehicle_type = request.args.get("vehicle_type")  # optional filter
    ev_only = request.args.get("ev_only") == "1"
    covered_only = request.args.get("covered_only") == "1"

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required"}), 400

    facilities = query("SELECT * FROM parking_facilities WHERE status='approved'")
    if ev_only:
        facilities = [f for f in facilities if f["ev_charging"]]
    if covered_only:
        facilities = [f for f in facilities if f["covered"]]

    results = nearby_parking(lat, lng, facilities, radius_km=radius)
    for r in results:
        avail = _current_availability(r["id"])
        r["available_slots"] = avail["free_total"]
        r["total_slots"] = avail["total"]

    return jsonify(results)


@parking_bp.route("/recommend", methods=["GET"])
def recommend_parking():
    """AI-ranked parking near a destination for a planned arrival time."""
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    radius = request.args.get("radius_km", default=5.0, type=float)
    arrival_str = request.args.get("arrival")  # ISO format, e.g. 2026-08-25T19:30:00
    vehicle_type = request.args.get("vehicle_type", "4-wheeler")

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required"}), 400

    arrival_dt = datetime.datetime.fromisoformat(arrival_str) if arrival_str else datetime.datetime.now()

    facilities = query("SELECT * FROM parking_facilities WHERE status='approved'")
    nearby = nearby_parking(lat, lng, facilities, radius_km=radius)

    candidates = []
    for f in nearby:
        avail = _current_availability(f["id"])
        price = f["price_4w"] if vehicle_type == "4-wheeler" else f["price_2w"]
        capacity = f["capacity_4w"] if vehicle_type == "4-wheeler" else f["capacity_2w"]
        candidates.append({
            "id": f["id"], "name": f["name"], "address": f["address"],
            "distance_km": f["distance_km"], "eta_minutes": f["eta_minutes"],
            "price_per_hour": price, "capacity": max(capacity, 1),
            "current_available": avail["free_total"], "rating": f["rating"] or 3.5,
        })

    ranked = recommend(candidates, arrival_dt)
    return jsonify({"arrival": arrival_dt.isoformat(), "results": ranked})


@parking_bp.route("/<int:facility_id>", methods=["GET"])
def facility_details(facility_id):
    f = query("SELECT * FROM parking_facilities WHERE id=?", (facility_id,), fetch="one")
    if not f:
        return jsonify({"error": "not found"}), 404
    avail = _current_availability(facility_id)
    f["available_slots"] = avail["free_total"]
    f["total_slots"] = avail["total"]
    reviews = query(
        "SELECT rating, comment, created_at FROM reviews WHERE parking_id=? ORDER BY created_at DESC LIMIT 10",
        (facility_id,),
    )
    f["recent_reviews"] = reviews
    return jsonify(f)
