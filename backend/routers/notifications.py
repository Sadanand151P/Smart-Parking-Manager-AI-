from flask import Blueprint, jsonify, g
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import query
from utils.auth_decorator import login_required

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.route("", methods=["GET"])
@login_required()
def list_notifications():
    rows = query(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY sent_at DESC LIMIT 50",
        (g.user_id,),
    )
    return jsonify(rows)
