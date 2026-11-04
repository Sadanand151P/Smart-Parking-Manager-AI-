"""
Model 1 — Parking Demand Prediction.

Predicts expected number of vehicles (occupancy) for a facility at a given
future hour/context. Same feature set as availability_prediction.py but
trained on `occupied` rather than `available` — kept as a separate model
(rather than deriving demand = capacity - availability) because in
production demand should also fold in queued/turned-away vehicles that
availability alone doesn't capture.
"""

import importlib
import os


def _load_pandas():
    try:
        return importlib.import_module("pandas")
    except (ImportError, ModuleNotFoundError) as exc:
        raise ImportError(
            "pandas is required for demand prediction. Install it in the active "
            "Python environment with `python -m pip install pandas`."
        ) from exc


pd = _load_pandas()
# pyright: reportMissingImports=false
try:
    joblib = importlib.import_module("joblib")
except (ImportError, ModuleNotFoundError) as exc:
    raise ImportError(
        "joblib is required for demand prediction. Install it in the active "
        "Python environment with `python -m pip install joblib`."
    ) from exc
try:
    sklearn_ensemble = importlib.import_module("sklearn.ensemble")
    sklearn_model_selection = importlib.import_module("sklearn.model_selection")
    sklearn_metrics = importlib.import_module("sklearn.metrics")
    RandomForestRegressor = sklearn_ensemble.RandomForestRegressor
    train_test_split = sklearn_model_selection.train_test_split
    mean_absolute_error = sklearn_metrics.mean_absolute_error
    r2_score = sklearn_metrics.r2_score
except (ImportError, ModuleNotFoundError, AttributeError) as exc:
    raise ImportError(
        "scikit-learn is required for demand prediction. Install it in the active "
        "Python environment with `python -m pip install scikit-learn`."
    ) from exc

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "parking_dataset.csv")
MODEL_PATH = os.path.join(BASE_DIR, "ml", "models", "demand_model.joblib")

FEATURES = ["parking_id", "capacity", "hour", "day_of_week", "is_weekend",
            "is_holiday", "weather_bad", "nearby_event"]
TARGET = "occupied"


def train():
    df = pd.read_csv(DATA_PATH)
    X, y = df[FEATURES], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    print(f"[demand_model] MAE={mae:.2f} vehicles, R2={r2:.3f}")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"[demand_model] saved -> {MODEL_PATH}")
    return model, {"mae": mae, "r2": r2}


def _load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Demand model not trained yet. Run `python3 ml/train.py` first.")
    return joblib.load(MODEL_PATH)


def predict_demand(parking_id: int, capacity: int, hour: int, day_of_week: int,
                    is_weekend: int = 0, is_holiday: int = 0,
                    weather_bad: int = 0, nearby_event: int = 0) -> dict:
    model = _load_model()
    x = pd.DataFrame([{
        "parking_id": parking_id, "capacity": capacity, "hour": hour,
        "day_of_week": day_of_week, "is_weekend": is_weekend, "is_holiday": is_holiday,
        "weather_bad": weather_bad, "nearby_event": nearby_event,
    }])
    predicted = float(model.predict(x)[0])
    predicted = max(0, min(capacity, round(predicted)))

    level = "LOW"
    ratio = predicted / max(capacity, 1)
    if ratio > 0.85:
        level = "VERY HIGH"
    elif ratio > 0.65:
        level = "HIGH"
    elif ratio > 0.35:
        level = "MODERATE"

    return {"predicted_demand": predicted, "demand_level": level}


if __name__ == "__main__":
    train()
