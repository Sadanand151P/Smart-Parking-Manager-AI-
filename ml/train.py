"""
Trains all ML models in sequence. Run this after generate_dataset.py.

Usage:
    python3 ml/generate_dataset.py
    python3 ml/train.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import demand_prediction
import availability_prediction

if __name__ == "__main__":
    print("=" * 60)
    print("SmartPark India — training ML models")
    print("=" * 60)

    print("\n[1/2] Demand Prediction Model")
    _, demand_metrics = demand_prediction.train()

    print("\n[2/2] Availability Prediction Model")
    _, avail_metrics = availability_prediction.train()

    print("\n" + "=" * 60)
    print("Training complete.")
    print(f"  Demand model       — MAE {demand_metrics['mae']:.2f}, R2 {demand_metrics['r2']:.3f}")
    print(f"  Availability model — MAE {avail_metrics['mae']:.2f}, R2 {avail_metrics['r2']:.3f}")
    print("=" * 60)
