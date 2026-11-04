"""
Generates a synthetic historical occupancy dataset for training the demand
and availability prediction models, since a fresh college project has no
real historical bookings yet. Once live, `ml/train.py` should instead pull
from the `parking_occupancy` and `bookings` tables — the feature columns
below (hour, day_of_week, is_weekend, is_holiday, capacity, base_occupancy,
weather_bad, nearby_event) match what those real tables can produce.

Run:  python3 ml/generate_dataset.py
"""

import numpy as np
import pandas as pd
import os

np.random.seed(42)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(BASE_DIR, "data", "parking_dataset.csv")

FACILITIES = [
    {"parking_id": 1, "name": "Phoenix Mall Parking", "city": "Lucknow", "capacity": 500},
    {"parking_id": 2, "name": "City Mall Parking", "city": "Lucknow", "capacity": 300},
    {"parking_id": 3, "name": "Metro Parking Hazratganj", "city": "Lucknow", "capacity": 150},
    {"parking_id": 4, "name": "Connaught Place Parking", "city": "Delhi", "capacity": 600},
    {"parking_id": 5, "name": "Phoenix Marketcity Parking", "city": "Mumbai", "capacity": 800},
    {"parking_id": 6, "name": "MG Road Parking", "city": "Bengaluru", "capacity": 400},
]

INDIAN_HOLIDAYS_2026_SAMPLE = {(1, 26), (3, 4), (8, 15), (10, 2), (10, 20), (12, 25)}


def occupancy_curve(hour: int) -> float:
    """Base occupancy fraction (0-1) by hour, roughly modelling a mall/market:
    quiet mornings, lunchtime bump, evening peak 18:00-21:00, quiet nights."""
    curve = {
        0: 0.05, 1: 0.03, 2: 0.02, 3: 0.02, 4: 0.03, 5: 0.05,
        6: 0.10, 7: 0.18, 8: 0.28, 9: 0.35, 10: 0.42, 11: 0.50,
        12: 0.58, 13: 0.60, 14: 0.55, 15: 0.52, 16: 0.55, 17: 0.65,
        18: 0.78, 19: 0.88, 20: 0.92, 21: 0.85, 22: 0.55, 23: 0.20,
    }
    return curve[hour]


def generate(days: int = 180) -> pd.DataFrame:
    rows = []
    start = pd.Timestamp("2026-01-01")
    for day_offset in range(days):
        date = start + pd.Timedelta(days=day_offset)
        dow = date.dayofweek  # 0=Mon
        is_weekend = 1 if dow >= 5 else 0
        is_holiday = 1 if (date.month, date.day) in INDIAN_HOLIDAYS_2026_SAMPLE else 0
        weather_bad = 1 if np.random.rand() < 0.08 else 0
        nearby_event = 1 if np.random.rand() < 0.05 else 0

        for fac in FACILITIES:
            for hour in range(24):
                base = occupancy_curve(hour)
                weekend_boost = 0.12 if is_weekend else 0
                holiday_boost = 0.15 if is_holiday else 0
                event_boost = 0.20 if nearby_event else 0
                weather_penalty = -0.10 if weather_bad else 0
                noise = np.random.normal(0, 0.05)

                occ_fraction = np.clip(
                    base + weekend_boost + holiday_boost + event_boost + weather_penalty + noise, 0.0, 0.98
                )
                occupied = int(round(occ_fraction * fac["capacity"]))
                available = fac["capacity"] - occupied

                rows.append({
                    "parking_id": fac["parking_id"],
                    "parking_name": fac["name"],
                    "city": fac["city"],
                    "capacity": fac["capacity"],
                    "date": date.strftime("%Y-%m-%d"),
                    "hour": hour,
                    "day_of_week": dow,
                    "is_weekend": is_weekend,
                    "is_holiday": is_holiday,
                    "weather_bad": weather_bad,
                    "nearby_event": nearby_event,
                    "occupied": occupied,
                    "available": available,
                    "occupancy_rate": round(occ_fraction, 4),
                })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"[generate_dataset] wrote {len(df):,} rows -> {OUT_PATH}")
    print(df.head())
