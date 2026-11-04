"""
Seeds the database with a demo admin, a demo owner + a few approved parking
facilities (matching the ML dataset's parking_id 1-3 in Lucknow), and some
sample slot occupancy — so the frontend has something to show immediately
after `python3 backend/database/database.py` + this script, without
requiring manual registration first.

Run:  python3 backend/seed_demo_data.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database.database import init_db, query
from utils.security import hash_password

FACILITIES = [
    {"name": "Phoenix Mall Parking", "address": "Vibhuti Khand, Gomti Nagar", "city": "Lucknow",
     "state": "Uttar Pradesh", "pincode": "226010", "latitude": 26.8548, "longitude": 81.0192,
     "capacity_2w": 200, "capacity_4w": 300, "price_2w": 20, "price_4w": 50,
     "ev_charging": 1, "cctv": 1, "covered": 1, "security_guard": 1, "is_24x7": 1},
    {"name": "City Mall Parking", "address": "Aliganj", "city": "Lucknow", "state": "Uttar Pradesh",
     "pincode": "226024", "latitude": 26.8820, "longitude": 80.9410,
     "capacity_2w": 100, "capacity_4w": 200, "price_2w": 15, "price_4w": 40,
     "ev_charging": 0, "cctv": 1, "covered": 1, "security_guard": 1, "is_24x7": 0,
     "opening_time": "08:00", "closing_time": "22:00"},
    {"name": "Metro Parking Hazratganj", "address": "Hazratganj", "city": "Lucknow", "state": "Uttar Pradesh",
     "pincode": "226001", "latitude": 26.8500, "longitude": 80.9400,
     "capacity_2w": 60, "capacity_4w": 90, "price_2w": 10, "price_4w": 30,
     "ev_charging": 0, "cctv": 1, "covered": 0, "security_guard": 0, "is_24x7": 0,
     "opening_time": "07:00", "closing_time": "23:00"},
]


def seed():
    init_db(reset=True)

    admin_id = query(
        "INSERT INTO users (name, email, mobile, password_hash, role, is_verified) VALUES (?,?,?,?,?,1)",
        ("SmartPark Admin", "admin@smartpark.in", "9999900000", hash_password("Admin@123"), "admin"),
    )
    owner_id = query(
        "INSERT INTO users (name, email, mobile, password_hash, role, is_verified) VALUES (?,?,?,?,?,1)",
        ("Ramesh Gupta", "ramesh.owner@smartpark.in", "9999911111", hash_password("Owner@123"), "owner"),
    )
    customer_id = query(
        "INSERT INTO users (name, email, mobile, password_hash, role, is_verified) VALUES (?,?,?,?,?,1)",
        ("Aditi Sharma", "aditi@example.com", "9999922222", hash_password("Customer@123"), "customer"),
    )

    for f in FACILITIES:
        facility_id = query(
            """INSERT INTO parking_facilities
               (owner_id, name, address, city, state, pincode, latitude, longitude,
                capacity_2w, capacity_4w, price_2w, price_4w, ev_charging, cctv,
                covered, security_guard, opening_time, closing_time, is_24x7, status, rating, rating_count)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (owner_id, f["name"], f["address"], f["city"], f["state"], f["pincode"], f["latitude"], f["longitude"],
             f["capacity_2w"], f["capacity_4w"], f["price_2w"], f["price_4w"], f["ev_charging"], f["cctv"],
             f["covered"], f["security_guard"], f.get("opening_time", "00:00"), f.get("closing_time", "23:59"),
             f["is_24x7"], "approved", 4.3, 12),
        )
        for i in range(1, f["capacity_2w"] + 1):
            status = "occupied" if i <= f["capacity_2w"] * 0.6 else "free"
            query("INSERT INTO parking_slots (parking_id, slot_number, vehicle_type, status) VALUES (?,?,?,?)",
                  (facility_id, f"2W-{i:03d}", "2-wheeler", status))
        for i in range(1, f["capacity_4w"] + 1):
            status = "occupied" if i <= f["capacity_4w"] * 0.55 else "free"
            query("INSERT INTO parking_slots (parking_id, slot_number, vehicle_type, status) VALUES (?,?,?,?)",
                  (facility_id, f"4W-{i:03d}", "4-wheeler", status))

    vehicle_id = query(
        "INSERT INTO vehicles (user_id, vehicle_number, vehicle_type, vehicle_model) VALUES (?,?,?,?)",
        (customer_id, "UP32NR7783", "4-wheeler", "Hyundai Creta"),
    )

    print("Seed complete.")
    print(f"  Admin    login: admin@smartpark.in / Admin@123")
    print(f"  Owner    login: ramesh.owner@smartpark.in / Owner@123")
    print(f"  Customer login: aditi@example.com / Customer@123")
    print(f"  3 approved facilities in Lucknow, 1 demo vehicle (UP32NR7783)")


if __name__ == "__main__":
    seed()
