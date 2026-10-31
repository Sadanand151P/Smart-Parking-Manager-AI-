import os
import sys
from flask import Flask, jsonify, send_from_directory  # type: ignore[import-not-found]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from database.database import init_db, DB_PATH

from routers.auth import auth_bp
from routers.users import users_bp
from routers.vehicles import vehicles_bp
from routers.parking import parking_bp
from routers.bookings import bookings_bp
from routers.payments import payments_bp
from routers.notifications import notifications_bp
from routers.admin import admin_bp

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.config.from_object(Config)

for bp in (auth_bp, users_bp, vehicles_bp, parking_bp, bookings_bp, payments_bp, notifications_bp, admin_bp):
    app.register_blueprint(bp)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "SmartPark India API"})


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "internal server error"}), 500


# Serve the plain HTML/CSS/JS frontend from the same Flask process for the
# college build (single `python3 main.py` to run everything).
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=Config.DEBUG)
