"""
Model 2 — Parking Availability Prediction.

Predicts expected available slots at a given parking facility for a future
hour, given day-of-week/weekend/holiday/weather/event context. Uses a
RandomForestRegressor (scikit-learn) — the original spec named
XGBoost/Gradient Boosting; RandomForest is the closest available substitute
in this offline sandbox. In `ml/train.py`, swapping to
GradientBoostingRegressor or xgboost.XGBRegressor is a one-line change since
they share scikit-learn's fit/predict interface.

Also returns a rough confidence interval, derived from the spread across the
forest's individual trees rather than a fixed +/-, so it tightens on
well-represented hours/facilities and widens on sparse ones.
"""

import os
try:
    import pandas as pd  # pyright: ignore[reportMissingModuleSource]  # type: ignore[import-not-found]
except (ImportError, ModuleNotFoundError) as exc:
    raise ImportError(
        "pandas is required for availability prediction. Install it with `python -m pip install pandas`."
    ) from exc
try:
    import joblib  # pyright: ignore[reportMissingImports]  # type: ignore[import-not-found]
except (ImportError, ModuleNotFoundError) as exc:
    raise ImportError(
        "joblib is required for availability prediction. Install it with `python -m pip install joblib`."
    ) from exc
from sklearn.ensemble import RandomForestRegressor  # pyright: ignore[reportMissingModuleSource]  # type: ignore[import-not-found]
try:
    from sklearn.model_selection import train_test_split  # pyright: ignore[reportMissingModuleSource]  # type: ignore[import-not-found]
except (ImportError, ModuleNotFoundError) as exc:
    raise ImportError(
        "scikit-learn is required for availability prediction. Install it with `python -m pip install scikit-learn`."
    ) from exc
try:
    from sklearn.metrics import mean_absolute_error, r2_score  # pyright: ignore[reportMissingModuleSource]  # type: ignore[import-not-found]
except (ImportError, ModuleNotFoundError) as exc:
    raise ImportError(
        "scikit-learn is required for availability prediction. Install it with `python -m pip install scikit-learn`."
    ) from exc

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "parking_dataset.csv")
MODEL_PATH = os.path.join(BASE_DIR, "ml", "models", "availability_model.joblib")

FEATURES = ["parking_id", "capacity", "hour", "day_of_week", "is_weekend",
            "is_holiday", "weather_bad", "nearby_event"]
TARGET = "available"


def train():
    df = pd.read_csv(DATA_PATH)
    X, y = df[FEATURES], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    print(f"[availability_model] MAE={mae:.2f} slots, R2={r2:.3f}")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"[availability_model] saved -> {MODEL_PATH}")
    return model, {"mae": mae, "r2": r2}


def _load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Availability model not trained yet. Run `python3 ml/train.py` first.")
    return joblib.load(MODEL_PATH)


def predict_availability(parking_id: int, capacity: int, hour: int, day_of_week: int,
                          is_weekend: int = 0, is_holiday: int = 0,
                          weather_bad: int = 0, nearby_event: int = 0) -> dict:
    model = _load_model()
    x = pd.DataFrame([{
        "parking_id": parking_id, "capacity": capacity, "hour": hour,
        "day_of_week": day_of_week, "is_weekend": is_weekend, "is_holiday": is_holiday,
        "weather_bad": weather_bad, "nearby_event": nearby_event,
    }])

    x_arr = x.values
    tree_preds = [float(tree.predict(x_arr)[0]) for tree in model.estimators_]
    mean_pred = min(max(sum(tree_preds) / len(tree_preds), 0), capacity)
    variance = sum((prediction - sum(tree_preds) / len(tree_preds)) ** 2
                   for prediction in tree_preds) / len(tree_preds)
    std_pred = variance ** 0.5

    low = max(0, round(mean_pred - std_pred))
    high = min(capacity, round(mean_pred + std_pred))
    # Confidence heuristic: tighter spread relative to capacity -> higher confidence.
    confidence = min(max(1 - (std_pred / max(capacity, 1)) * 3, 0.4), 0.97)

    return {
        "predicted_available": round(mean_pred),
        "range_low": low,
        "range_high": high,
        "confidence": round(confidence, 2),
    }


if __name__ == "__main__":
    train()
