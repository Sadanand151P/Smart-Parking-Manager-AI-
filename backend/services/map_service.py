"""
Map/geo service.

Provides distance calculation (Haversine — no external dependency) and a
provider-agnostic interface for geocoding/nearby search. MAP_API_KEY is
absent in this dev build, so geocode() and directions() fall back to a
mock. In production, point this module at Google Maps Platform
(Geocoding + Places + Routes) or Mappls (India-first: maps, nearby search,
routing/traffic) — the routers never call the provider SDK directly, only
this module, so switching providers later is a one-file change.
"""

import os
import math

MAP_API_KEY = os.environ.get("MAP_API_KEY", "")
USE_MOCK = not bool(MAP_API_KEY)
PROVIDER = os.environ.get("MAP_PROVIDER", "mappls")  # "google" | "mappls"


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def estimate_travel_minutes(distance_km: float, avg_speed_kmph: float = 22.0) -> int:
    """Rough city-traffic estimate. Replace with provider's real ETA (Google
    Routes / Mappls routing API) when MAP_API_KEY is configured."""
    return max(1, round((distance_km / avg_speed_kmph) * 60))


def geocode(address: str) -> dict:
    """Address -> {lat, lng}. Mocked here; in production call
    Google Geocoding API or Mappls Geocoding API."""
    if USE_MOCK:
        # Deterministic pseudo-geocode for demo purposes only.
        h = abs(hash(address))
        lat = 8.0 + (h % 2200) / 100.0   # spans roughly across India's latitude range
        lng = 68.0 + (h % 2900) / 100.0  # spans roughly across India's longitude range
        return {"lat": round(lat, 6), "lng": round(lng, 6), "provider": "mock"}
    raise NotImplementedError(f"Wire up {PROVIDER} geocoding here with MAP_API_KEY.")


def nearby_parking(lat: float, lng: float, facilities: list, radius_km: float = 5.0) -> list:
    """Given a list of facility dicts (each with latitude/longitude), return
    those within radius_km, annotated with distance_km, sorted nearest first."""
    results = []
    for f in facilities:
        d = haversine_km(lat, lng, f["latitude"], f["longitude"])
        if d <= radius_km:
            f = dict(f)
            f["distance_km"] = round(d, 2)
            f["eta_minutes"] = estimate_travel_minutes(d)
            results.append(f)
    return sorted(results, key=lambda x: x["distance_km"])
