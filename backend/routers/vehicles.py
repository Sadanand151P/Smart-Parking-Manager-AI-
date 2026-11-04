from flask import Blueprint, request, jsonify, g
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import query
from utils.auth_decorator import login_required
from utils.validation import is_valid_vehicle_number, normalize_vehicle_number, sanitize_str

vehicles_bp = Blueprint("vehicles", __name__, url_prefix="/api/vehicles")


@vehicles_bp.route("", methods=["GET"])
@login_required()
def list_vehicles():
    rows = query("SELECT * FROM vehicles WHERE user_id=? ORDER BY created_at DESC", (g.user_id,))
    return jsonify(rows)


@vehicles_bp.route("", methods=["POST"])
@login_required()
def add_vehicle():
    data = request.get_json(force=True)
    raw_number = sanitize_str(data.get("vehicle_number"))
    vehicle_type = data.get("vehicle_type")
    model = sanitize_str(data.get("vehicle_model", ""))

    if vehicle_type not in ("2-wheeler", "4-wheeler", "ev"):
        return jsonify({"error": "vehicle_type must be 2-wheeler, 4-wheeler, or ev"}), 400
    if not is_valid_vehicle_number(raw_number):
        return jsonify({"error": "invalid Indian vehicle registration number, e.g. UP32NR7783"}), 400

    number = normalize_vehicle_number(raw_number)
    existing = query("SELECT id FROM vehicles WHERE user_id=? AND vehicle_number=?",
                     (g.user_id, number), fetch="one")
    if existing:
        return jsonify({"error": "vehicle already added"}), 409

    vehicle_id = query(
        "INSERT INTO vehicles (user_id, vehicle_number, vehicle_type, vehicle_model) VALUES (?, ?, ?, ?)",
        (g.user_id, number, vehicle_type, model),
    )
    return jsonify({"message": "vehicle added", "vehicle_id": vehicle_id, "vehicle_number": number}), 201


@vehicles_bp.route("/<int:vehicle_id>", methods=["DELETE"])
@login_required()
def delete_vehicle(vehicle_id):
    owned = query("SELECT id FROM vehicles WHERE id=? AND user_id=?", (vehicle_id, g.user_id), fetch="one")
    if not owned:
        return jsonify({"error": "vehicle not found"}), 404
    query("DELETE FROM vehicles WHERE id=?", (vehicle_id,))
    return jsonify({"message": "vehicle removed"})
