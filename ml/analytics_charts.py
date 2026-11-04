"""
Generates the static analytics charts called for in the spec (line, bar,
pie, histogram, heatmap, scatter — occupancy trend & demand) for inclusion
in the BCA project report/PPT. Reads from the synthetic training dataset by
default; once real bookings exist, point DATA_SOURCE at a live export of
the `bookings`/`parking_occupancy` tables instead.

Run:  python3 ml/analytics_charts.py
Output: data/charts/*.png
"""

import os
import pandas as pd  # type: ignore[import-not-found]
try:
    import matplotlib  # type: ignore[reportMissingModuleSource]
except ImportError as exc:
    raise ImportError(
        "matplotlib is required to generate analytics charts. "
        "Install it in the active Python environment with: python -m pip install matplotlib"
    ) from exc

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # type: ignore[reportMissingModuleSource]
import seaborn as sns  # type: ignore[reportMissingModuleSource]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "parking_dataset.csv")
OUT_DIR = os.path.join(BASE_DIR, "data", "charts")

sns.set_theme(style="whitegrid")
ASPHALT = "#1C1E22"
YELLOW = "#F2C230"
GREEN = "#3FA34D"
RED = "#D64545"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])

    # 1. Line chart — average occupancy rate trend over time (all facilities)
    daily = df.groupby("date")["occupancy_rate"].mean()
    plt.figure(figsize=(10, 4))
    plt.plot(daily.index, daily.values, color=ASPHALT, linewidth=1.2)
    plt.title("Average Occupancy Rate Trend (All Facilities)")
    plt.ylabel("Occupancy rate")
    plt.xlabel("Date")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "01_occupancy_trend_line.png"), dpi=130)
    plt.close()

    # 2. Bar chart — average occupancy by hour of day (demand curve)
    hourly = df.groupby("hour")["occupancy_rate"].mean()
    plt.figure(figsize=(9, 4))
    plt.bar(hourly.index, hourly.values, color=YELLOW, edgecolor=ASPHALT)
    plt.title("Average Occupancy Rate by Hour of Day")
    plt.xlabel("Hour")
    plt.ylabel("Occupancy rate")
    plt.xticks(range(0, 24, 2))
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "02_hourly_demand_bar.png"), dpi=130)
    plt.close()

    # 3. Pie chart — booking share by facility (using occupied-vehicle-hours as proxy)
    by_facility = df.groupby("parking_name")["occupied"].sum()
    plt.figure(figsize=(6, 6))
    plt.pie(by_facility.values, labels=by_facility.index.tolist(), autopct="%1.1f%%",
            colors=sns.color_palette("YlOrBr", len(by_facility)))
    plt.title("Share of Total Occupied Vehicle-Hours by Facility")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "03_facility_share_pie.png"), dpi=130)
    plt.close()

    # 4. Histogram — distribution of occupancy rate
    plt.figure(figsize=(8, 4))
    plt.hist(df["occupancy_rate"], bins=30, color=GREEN, edgecolor=ASPHALT, alpha=0.85)
    plt.title("Distribution of Occupancy Rate (All Records)")
    plt.xlabel("Occupancy rate")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "04_occupancy_histogram.png"), dpi=130)
    plt.close()

    # 5. Heatmap — hour x day-of-week average occupancy (classic parking demand heatmap)
    pivot = df.pivot_table(values="occupancy_rate", index="hour", columns="day_of_week", aggfunc="mean")
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    plt.figure(figsize=(8, 8))
    sns.heatmap(pivot, cmap="YlOrRd", xticklabels=day_labels, cbar_kws={"label": "Occupancy rate"})
    plt.title("Occupancy Heatmap — Hour vs Day of Week")
    plt.xlabel("Day of week")
    plt.ylabel("Hour")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "05_occupancy_heatmap.png"), dpi=130)
    plt.close()

    # 6. Scatter — capacity vs occupied (does bigger facility mean more absolute demand?)
    sample = df.sample(min(3000, len(df)), random_state=42)
    plt.figure(figsize=(7, 5))
    plt.scatter(sample["capacity"], sample["occupied"], alpha=0.25, color=RED, s=12)
    plt.title("Capacity vs Occupied Vehicles (sampled)")
    plt.xlabel("Facility capacity")
    plt.ylabel("Occupied")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "06_capacity_vs_occupied_scatter.png"), dpi=130)
    plt.close()

    print(f"[analytics_charts] 6 charts saved -> {OUT_DIR}")


if __name__ == "__main__":
    main()
