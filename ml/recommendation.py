"""
Model 3 — Smart Parking Recommendation.

Starts as the weighted scoring system called for in the spec (distance,
price, availability, rating, predicted availability), normalized to a 0-100
"AI Score". Designed so it can be upgraded later to a learned
ranker (e.g. LightGBM LambdaRank / a pairwise model trained on click and
booking-conversion logs) without changing its call signature — `rank()`
always takes a list of candidate facilities and returns them sorted with a
`ai_score` field attached.
"""

from typing import List, Dict

DEFAULT_WEIGHTS = {
    "distance": 0.25,      # closer is better
    "price": 0.15,         # cheaper is better
    "availability": 0.25,  # more current availability is better
    "predicted_availability": 0.20,  # more predicted availability at arrival is better
    "rating": 0.15,        # higher rating is better
}


def _normalize(value, min_v, max_v, invert=False):
    if max_v == min_v:
        return 0.5
    n = (value - min_v) / (max_v - min_v)
    n = max(0.0, min(1.0, n))
    return 1 - n if invert else n


def rank(candidates: List[Dict], weights: Dict = None) -> List[Dict]:
    """
    Each candidate dict must have: distance_km, price_per_hour, availability,
    predicted_availability, rating.
    Returns the same list, sorted best-first, with 'ai_score' (0-100) added.
    """
    if not candidates:
        return []
    weights = weights or DEFAULT_WEIGHTS

    distances = [c["distance_km"] for c in candidates]
    prices = [c["price_per_hour"] for c in candidates]
    avail = [c["availability"] for c in candidates]
    pred_avail = [c["predicted_availability"] for c in candidates]
    ratings = [c["rating"] for c in candidates]

    scored = []
    for c in candidates:
        s_distance = _normalize(c["distance_km"], min(distances), max(distances), invert=True)
        s_price = _normalize(c["price_per_hour"], min(prices), max(prices), invert=True)
        s_avail = _normalize(c["availability"], min(avail), max(avail))
        s_pred = _normalize(c["predicted_availability"], min(pred_avail), max(pred_avail))
        s_rating = _normalize(c["rating"], min(ratings), max(ratings))

        score = (
            weights["distance"] * s_distance
            + weights["price"] * s_price
            + weights["availability"] * s_avail
            + weights["predicted_availability"] * s_pred
            + weights["rating"] * s_rating
        )
        c = dict(c)
        c["ai_score"] = round(score * 100, 1)
        scored.append(c)

    return sorted(scored, key=lambda x: x["ai_score"], reverse=True)


if __name__ == "__main__":
    demo = [
        {"name": "City Mall Parking", "distance_km": 0.8, "price_per_hour": 40,
         "availability": 35, "predicted_availability": 21, "rating": 4.6},
        {"name": "Metro Parking", "distance_km": 1.2, "price_per_hour": 30,
         "availability": 15, "predicted_availability": 10, "rating": 4.2},
    ]
    for r in rank(demo):
        print(r["name"], "->", r["ai_score"])
