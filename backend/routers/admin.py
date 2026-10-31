import datetime
try:
    from flask import Blueprint, request, jsonify, g  # type: ignore[import-not-found]
except ImportError:
    # Keep the module importable for tooling when Flask is not installed.
    class _FlaskUnavailable:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Flask is required to use the admin API")

        def route(self, *args, **kwargs):
            return lambda func: func

    Blueprint = _FlaskUnavailable
    request = g = None
    jsonify = lambda value: value
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import query

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ml"))
from utils.auth_decorator import login_required

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# ---------------------------------------------------------------- Facility approval

@admin_bp.route("/facilities/pending", methods=["GET"])
@login_required(roles=["admin"])
def pending_facilities():
    rows = query("SELECT * FROM parking_facilities WHERE status='pending' ORDER BY created_at")
    return jsonify(rows)


@admin_bp.route("/facilities/<int:facility_id>/approve", methods=["POST"])
@login_required(roles=["admin"])
def approve_facility(facility_id):
    query("UPDATE parking_facilities SET status='approved' WHERE id=?", (facility_id,))
    return jsonify({"message": "facility approved"})


@admin_bp.route("/facilities/<int:facility_id>/reject", methods=["POST"])
@login_required(roles=["admin"])
def reject_facility(facility_id):
    query("UPDATE parking_facilities SET status='rejected' WHERE id=?", (facility_id,))
    return jsonify({"message": "facility rejected"})


# ---------------------------------------------------------------- Users

@admin_bp.route("/users", methods=["GET"])
@login_required(roles=["admin"])
def list_users():
    rows = query("SELECT id, name, email, mobile, role, is_verified, created_at FROM users ORDER BY created_at DESC")
    return jsonify(rows)


# ---------------------------------------------------------------- Dashboard

@admin_bp.route("/dashboard", methods=["GET"])
@login_required(roles=["admin"])
def dashboard():
    total_facilities_row = query(
        "SELECT COUNT(*) as c FROM parking_facilities WHERE status='approved'", fetch="one"
    )
    total_facilities = (
        int(total_facilities_row.get("c", 0)) if isinstance(total_facilities_row, dict) else 0
    )

    total_users_row = query("SELECT COUNT(*) as c FROM users WHERE role='customer'", fetch="one")
    total_users = int(total_users_row.get("c", 0)) if isinstance(total_users_row, dict) else 0

    today = datetime.date.today().isoformat()
    todays_bookings_row = query(
        "SELECT COUNT(*) as c FROM bookings WHERE booking_date=?", (today,), fetch="one"
    )
    todays_bookings = int(todays_bookings_row.get("c", 0)) if isinstance(todays_bookings_row, dict) else 0

    active_vehicles_row = query(
        "SELECT COUNT(DISTINCT vehicle_id) as c FROM bookings WHERE booking_status='confirmed'",
        fetch="one",
    )
    active_vehicles = int(active_vehicles_row.get("c", 0)) if isinstance(active_vehicles_row, dict) else 0

    revenue_today_row = query(
        "SELECT COALESCE(SUM(amount),0) as r FROM bookings WHERE booking_date=? AND booking_status!='cancelled'",
        (today,), fetch="one",
    )
    revenue_today = float(revenue_today_row.get("r", 0)) if isinstance(revenue_today_row, dict) else 0.0

    peak = query(
        """SELECT start_time, COUNT(*) as c FROM bookings
           GROUP BY start_time ORDER BY c DESC LIMIT 1""", fetch="one"
    )

    return jsonify({
        "total_parking_facilities": total_facilities,
        "total_users": total_users,
        "todays_bookings": todays_bookings,
        "active_vehicles": active_vehicles,
        "revenue_today": revenue_today,
        "peak_booking_time": peak.get("start_time") if isinstance(peak, dict) and peak else None,
    })


# ---------------------------------------------------------------- Analytics (Data Science layer)

@admin_bp.route("/analytics/summary", methods=["GET"])
@login_required(roles=["admin"])
def analytics_summary():
    """Core DS analytics: bookings over time, revenue, occupancy rate,
    avg duration, most popular parking/city, vehicle-type split, cancellation rate."""
    import pandas as pd

    rows = query(
        """SELECT b.*, p.city, p.name as parking_name, v.vehicle_type
           FROM bookings b
           JOIN parking_facilities p ON p.id = b.parking_id
           JOIN vehicles v ON v.id = b.vehicle_id"""
    )
    if not rows:
        return jsonify({"message": "no booking data yet"})

    df = pd.DataFrame(rows)
    df["booking_date"] = pd.to_datetime(df["booking_date"])

    daily = df.groupby(df["booking_date"].dt.date).size().to_dict()
    weekly = df.groupby(df["booking_date"].dt.isocalendar().week).size().to_dict()
    monthly = df.groupby(df["booking_date"].dt.to_period("M").astype(str)).size().to_dict()

    total_revenue = float(df.loc[df.booking_status != "cancelled", "amount"].sum())
    cancellation_rate = float((df.booking_status == "cancelled").mean() * 100)
    most_popular_parking = df["parking_name"].value_counts().idxmax()
    most_popular_city = df["city"].value_counts().idxmax()
    vehicle_split = df["vehicle_type"].value_counts().to_dict()

    def to_hm(t):
        try:
            return datetime.datetime.strptime(t, "%H:%M")
        except Exception:
            return None

    durations = []
    for _, r in df.iterrows():
        t1, t2 = to_hm(r["start_time"]), to_hm(r["end_time"])
        if t1 and t2:
            durations.append(max(1.0, (t2 - t1).seconds / 3600))
    avg_duration_hours = round(sum(durations) / len(durations), 2) if durations else 0

    return jsonify({
        "daily_bookings": {str(k): v for k, v in daily.items()},
        "weekly_bookings": {str(k): v for k, v in weekly.items()},
        "monthly_bookings": monthly,
        "total_revenue": round(total_revenue, 2),
        "cancellation_rate_pct": round(cancellation_rate, 2),
        "avg_parking_duration_hours": avg_duration_hours,
        "most_popular_parking": most_popular_parking,
        "most_popular_city": most_popular_city,
        "vehicle_type_distribution": vehicle_split,
    })


@admin_bp.route("/analytics/ai-prediction", methods=["GET"])
@login_required(roles=["admin"])
def analytics_ai_prediction():
    """Surfaces the demand model's forecast for the current peak window across
    all approved facilities — feeds the 'AI Prediction' card on the admin dashboard."""
    try:
        ml_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "ml",
        )
        if ml_path not in sys.path:
            sys.path.insert(0, ml_path)
        from demand_prediction import predict_demand
    except FileNotFoundError:
        return jsonify({"error": "demand model not trained — run `python3 ml/train.py`"}), 503

    facilities = query("SELECT id, name, capacity_2w, capacity_4w FROM parking_facilities WHERE status='approved'")
    now = datetime.datetime.now()
    predictions = []
    for f in facilities:
        capacity = f["capacity_2w"] + f["capacity_4w"]
        try:
            result = predict_demand(f["id"], capacity, now.hour, now.weekday())
            predictions.append({"parking_id": f["id"], "name": f["name"], **result})
        except FileNotFoundError:
            continue

    overall_level = "LOW"
    if predictions:
        levels = [p["demand_level"] for p in predictions]
        if "VERY HIGH" in levels:
            overall_level = "VERY HIGH"
        elif "HIGH" in levels:
            overall_level = "HIGH"
        elif "MODERATE" in levels:
            overall_level = "MODERATE"

    return jsonify({"as_of": now.isoformat(), "overall_demand_level": overall_level, "facilities": predictions})
