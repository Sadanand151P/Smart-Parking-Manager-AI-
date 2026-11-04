"""
Bridges the ML models (ml/) into the app layer: given a list of nearby
facilities (from map_service.nearby_parking) plus an arrival time, attaches
predicted availability/demand and an AI recommendation score to each.
Falls back to a simple heuristic if the models haven't been trained yet
(fresh checkout), so the app never hard-fails for a missing .joblib file.
"""

import os
import sys
import datetime
import importlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ml"))

try:
    from ml.availability_prediction import predict_availability
    from ml.demand_prediction import predict_demand
    _ML_AVAILABLE = True
except Exception:
    # The ML modules are imported dynamically via sys.path, which static analyzers
    # may not resolve. If either model is unavailable at runtime, the service must
    # still continue using the fallback heuristic.
    _ML_AVAILABLE = False
    predict_availability = None
    predict_demand = None

try:
    rank_candidates = importlib.import_module("recommendation").rank
except ModuleNotFoundError:
    rank_candidates = importlib.import_module("ml.recommendation").rank


def _heuristic_availability(current_available, capacity, hour):
    """Used only if the trained models are missing — simple evening-peak dip."""
    peak_hours = {18, 19, 20, 21}
    factor = 0.6 if hour in peak_hours else 0.9
    predicted = max(0, round(current_available * factor))
    return {"predicted_available": predicted, "range_low": max(0, predicted - 5),
            "range_high": min(capacity, predicted + 5), "confidence": 0.55}


def recommend(facilities: list, arrival_dt: datetime.datetime, is_holiday: int = 0,
              weather_bad: int = 0, nearby_event: int = 0) -> list:
    """
    facilities: list of dicts with at least
      id, name, distance_km, price_per_hour, capacity, current_available, rating
    Returns the list annotated with predicted_availability, demand_level, ai_score,
    sorted best-first.
    """
    hour = arrival_dt.hour
    dow = arrival_dt.weekday()
    is_weekend = 1 if dow >= 5 else 0

    candidates = []
    for f in facilities:
        if _ML_AVAILABLE and predict_availability is not None and predict_demand is not None:
            try:
                avail = predict_availability(
                    parking_id=f["id"], capacity=f["capacity"], hour=hour, day_of_week=dow,
                    is_weekend=is_weekend, is_holiday=is_holiday,
                    weather_bad=weather_bad, nearby_event=nearby_event,
                )
                demand = predict_demand(
                    parking_id=f["id"], capacity=f["capacity"], hour=hour, day_of_week=dow,
                    is_weekend=is_weekend, is_holiday=is_holiday,
                    weather_bad=weather_bad, nearby_event=nearby_event,
                )
            except FileNotFoundError:
                avail = _heuristic_availability(f["current_available"], f["capacity"], hour)
                demand = {"demand_level": "UNKNOWN"}
        else:
            avail = _heuristic_availability(f["current_available"], f["capacity"], hour)
            demand = {"demand_level": "UNKNOWN"}

        candidates.append({
            **f,
            "predicted_availability": avail["predicted_available"],
            "predicted_range": [avail["range_low"], avail["range_high"]],
            "prediction_confidence": avail["confidence"],
            "demand_level": demand["demand_level"],
            "availability": f["current_available"],
        })

    return rank_candidates(candidates)
