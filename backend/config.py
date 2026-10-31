import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.environ.get("JWT_SECRET", "dev-secret-change-me-in-.env")
    DEBUG = os.environ.get("DEBUG", "1") == "1"
    BOOKING_EXPIRY_MINUTES = 15   # unpaid bookings auto-expire after this
    REMINDER_MINUTES_BEFORE = 30  # send reminder SMS this long before start_time
