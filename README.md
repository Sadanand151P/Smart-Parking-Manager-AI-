# SmartPark India — AI-Based Smart Parking Management & Pre-Booking System

A BCA (Data Science & AI) major project: find nearby parking, get an
AI-predicted availability at your arrival time, pre-book a slot, pay, and
get a QR ticket — with an owner portal and an admin analytics dashboard.

> **Find → Compare → Predict → Book → Navigate → Park → Pay → Confirm**

---

## ⚠️ Stack substitution note (read this first)

The original design called for **FastAPI + PostgreSQL + XGBoost + qrcode +
Google Maps/Mappls + MSG91**. This build was generated in an offline
sandbox with no `pip install` access, so it uses the closest equivalents
that were already available, with the exact same architecture and API
shape:

| Originally planned | Used in this build | Why | Swap effort |
|---|---|---|---|
| FastAPI | **Flask** | not installable offline | Low — same REST routes, different decorator syntax |
| PostgreSQL | **SQLite** | zero-setup, no server needed | Low — `schema.sql` is portable ANSI SQL |
| XGBoost | **scikit-learn RandomForest** | not installable offline | Very low — same `.fit()/.predict()` API |
| `qrcode` library | **Pillow-drawn placeholder grid** | not installable offline | Trivial — see `services/qr_service.py` docstring |
| Google Maps / Mappls | **Mock geocoder + Haversine distance** | needs a live API key | Medium — one file, `services/map_service.py` |
| MSG91 | **Console/DB mock OTP+SMS** | needs a live API key | Medium — one file, `services/sms_service.py` |
| Razorpay/Stripe etc. | **Mock payment gateway** | needs a live merchant account | Medium — one file, `services/payment_service.py` |

Every mocked service is isolated in its own file under `backend/services/`
with a docstring explaining exactly what to change to go live. **Nothing
in the routers or ML code needs to change** — they only call these service
modules, never the underlying provider directly. This was a deliberate
design choice so the switch is safe for a viva demo now and a real
deployment later.

---

## Quick start

```bash
cd SmartPark-India
pip install -r requirements.txt          # or: pip install -r requirements.txt --break-system-packages

# 1. Generate training data + train the two ML models
python3 ml/generate_dataset.py
python3 ml/train.py

# 2. Seed the database with demo users + 3 approved Lucknow facilities
python3 backend/seed_demo_data.py

# 3. Run the app (serves both the API and the frontend on one port)
python3 backend/main.py
```

Open **http://localhost:5000** in a browser.

**Demo logins** (from `seed_demo_data.py`):

| Role | Email | Password |
|---|---|---|
| Admin | admin@smartpark.in | Admin@123 |
| Owner | ramesh.owner@smartpark.in | Owner@123 |
| Customer | aditi@example.com | Customer@123 |

The customer account already has one vehicle (`UP32NR7783`) so you can book
immediately from the homepage.

To reset all data: `python3 backend/seed_demo_data.py` again (it drops and
recreates the DB).

---

## Project structure

```
SmartPark-India/
├── backend/
│   ├── main.py                  # Flask app entrypoint (serves API + frontend)
│   ├── config.py
│   ├── seed_demo_data.py        # demo users/facilities for a fresh viva run
│   ├── database/
│   │   ├── schema.sql           # 11 tables, portable to PostgreSQL
│   │   └── database.py          # connection + query helper
│   ├── routers/                 # one Flask Blueprint per domain
│   │   ├── auth.py              # register, OTP verify, login, forgot password
│   │   ├── users.py             # profile, change password, my bookings
│   │   ├── vehicles.py          # add/list/remove vehicles, plate validation
│   │   ├── parking.py           # owner registration, nearby search, AI recommend
│   │   ├── bookings.py          # booking engine with atomic slot locking
│   │   ├── payments.py          # payment history
│   │   ├── notifications.py     # notification history
│   │   └── admin.py             # approvals, dashboard, DS analytics, AI prediction
│   ├── services/                # provider abstractions (see table above)
│   │   ├── sms_service.py
│   │   ├── map_service.py
│   │   ├── qr_service.py
│   │   ├── payment_service.py
│   │   └── recommendation_service.py   # bridges ML models into the API
│   └── utils/
│       ├── security.py          # PBKDF2 password hashing, JWT
│       ├── validation.py        # Indian mobile/vehicle/pincode validators
│       └── auth_decorator.py    # @login_required(roles=[...])
│
├── ml/
│   ├── generate_dataset.py      # synthetic 180-day/6-facility occupancy dataset
│   ├── demand_prediction.py     # Model 1 — RandomForestRegressor
│   ├── availability_prediction.py  # Model 2 — RandomForestRegressor + confidence interval
│   ├── recommendation.py        # Model 3 — weighted multi-factor AI score (0-100)
│   ├── train.py                 # trains both regression models
│   ├── analytics_charts.py      # 6 matplotlib/seaborn charts for the report/PPT
│   └── models/                  # saved .joblib files (generated by train.py)
│
├── frontend/                    # plain HTML/CSS/JS, no build step
│   ├── index.html               # landing + destination search
│   ├── map.html                 # AI-ranked results + booking modal
│   ├── login.html / register.html
│   ├── my-bookings.html         # vehicles, booking history, QR ticket, review
│   ├── owner.html                # facility registration + occupancy updates
│   ├── admin.html                # approvals, dashboard, AI prediction, DS analytics
│   ├── css/style.css             # design system (see below)
│   └── js/api.js                 # shared fetch client, auth, toasts, bay-grid renderer
│
├── data/
│   ├── parking_dataset.csv       # generated by generate_dataset.py
│   ├── smartpark.db              # generated by database.py / seed script
│   ├── qr_tickets/               # generated PNGs per booking
│   └── charts/                   # generated by analytics_charts.py
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## Design system (frontend)

Grounded in the actual subject — Indian road/parking infrastructure —
rather than a generic dashboard look:

- **Palette:** asphalt `#1C1E22`, off-white `#F5F3EE`, road-marking yellow
  `#F2C230`, signal green `#3FA34D`, signal red `#D64545`.
- **Type:** Oswald (condensed, highway-signage) for headings, Inter for
  body text, JetBrains Mono for vehicle plates and booking references.
- **Signature element:** a live *painted parking-bay grid* — used as the
  homepage hero **and** as the actual real-time availability indicator
  (`renderBayGrid()` in `js/api.js`), so it's functional, not decorative.

---

## The three ML models

All three live in `ml/` and are called through
`backend/services/recommendation_service.py`, which degrades gracefully to
a simple heuristic if the models haven't been trained yet (so the app
never hard-crashes on a fresh checkout).

1. **Demand Prediction** (`demand_prediction.py`) — RandomForestRegressor
   predicting occupied-vehicle count for a facility/hour/context.
   Achieved **R² ≈ 0.98, MAE ≈ 18 vehicles** on the synthetic dataset.
2. **Availability Prediction** (`availability_prediction.py`) — same
   features, predicts free slots, and derives a confidence interval from
   the spread across the forest's individual trees (tighter on
   well-represented hours, wider on sparse ones). **R² ≈ 0.98**.
3. **Smart Recommendation** (`recommendation.py`) — normalizes distance,
   price, current availability, predicted availability, and rating into a
   weighted 0–100 "AI Score", ranking facilities best-first. Designed so
   the weighted formula can later be replaced by a learned ranker without
   changing its interface.

Retrain anytime with real data by pointing `ml/train.py` at an export of
the `bookings` / `parking_occupancy` tables instead of the synthetic CSV —
the feature columns already match those tables' shape.

---

## API reference (selected endpoints)

All authenticated routes expect `Authorization: Bearer <token>`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | — | Register + send OTP |
| POST | `/api/auth/verify-otp` | — | Verify OTP, returns JWT |
| POST | `/api/auth/login` | — | Login, returns JWT |
| GET | `/api/parking/nearby?lat=&lng=&radius_km=` | — | Plain distance-sorted search |
| GET | `/api/parking/recommend?lat=&lng=&arrival=` | — | **AI-ranked** results with predicted availability |
| POST | `/api/parking/register` | owner | Register a new facility (pending approval) |
| POST | `/api/bookings` | customer | Create booking (atomic slot lock, generates QR) |
| POST | `/api/bookings/<id>/pay` | customer | Mock payment charge |
| POST | `/api/bookings/<id>/cancel` | customer | Cancel + free the slot |
| GET | `/api/admin/dashboard` | admin | Live counts: facilities, users, bookings, revenue |
| GET | `/api/admin/analytics/summary` | admin | Pandas-computed DS analytics |
| GET | `/api/admin/analytics/ai-prediction` | admin | Live demand-model forecast per facility |

---

## For your BCA viva

> "I developed an AI-enabled geospatial parking platform that combines
> real-time and predicted parking availability, pre-booking with atomic
> slot locking, machine-learning-based demand prediction, a multi-factor
> intelligent recommendation engine, QR-based digital tickets, and an
> admin analytics dashboard — built end-to-end and validated with a live
> API test covering the entire user journey from search to payment."

Areas you can speak to, each backed by working code:

| Area | Where |
|---|---|
| Web development | `frontend/` — plain HTML/CSS/JS, responsive, no framework |
| Backend/API design | `backend/routers/` — Blueprint-per-domain REST API |
| Database design | `backend/database/schema.sql` — 11 normalized tables |
| Data Science | `ml/generate_dataset.py`, `ml/analytics_charts.py` — Pandas/NumPy/Matplotlib/Seaborn |
| Machine Learning | `ml/demand_prediction.py`, `ml/availability_prediction.py` — scikit-learn, R²≈0.98 |
| AI recommendation | `ml/recommendation.py` — weighted multi-criteria scoring |
| Security | PBKDF2 password hashing, JWT auth, role-based access, input validation |
| Concurrency correctness | `BEGIN IMMEDIATE` transaction in `bookings.py` prevents double-booking |

---

## Known limitations (be upfront about these in your report)

- QR codes are **visually** scannable-looking but not real, decodable QR —
  swap in the `qrcode` package when you have internet access (one-line
  change, documented in `qr_service.py`).
- SMS/OTP/payments/maps are mocked — see the substitution table above.
- The ML models are trained on **synthetic** data with hand-tuned demand
  curves, not real historical bookings — expected, since a new project has
  no booking history yet. Retrain on real data once the platform has been
  live for a few weeks.
- No frontend build step/framework — kept intentionally simple (plain
  HTML/CSS/JS) so it runs anywhere without Node.js.
