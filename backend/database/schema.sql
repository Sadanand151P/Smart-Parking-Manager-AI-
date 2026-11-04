-- ============================================================
-- SmartPark India — Database Schema (SQLite, portable to Postgres)
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    mobile TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer', -- customer | owner | admin
    is_verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS otp_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile TEXT NOT NULL,
    code TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT 'login', -- login | register | reset
    expires_at TEXT NOT NULL,
    is_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vehicle_number TEXT NOT NULL,
    vehicle_type TEXT NOT NULL, -- 2-wheeler | 4-wheeler | ev
    vehicle_model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, vehicle_number)
);

CREATE TABLE IF NOT EXISTS parking_facilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    pincode TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    capacity_2w INTEGER NOT NULL DEFAULT 0,
    capacity_4w INTEGER NOT NULL DEFAULT 0,
    price_2w REAL NOT NULL DEFAULT 0,
    price_4w REAL NOT NULL DEFAULT 0,
    ev_charging INTEGER NOT NULL DEFAULT 0,
    cctv INTEGER NOT NULL DEFAULT 0,
    covered INTEGER NOT NULL DEFAULT 0,
    security_guard INTEGER NOT NULL DEFAULT 0,
    opening_time TEXT NOT NULL DEFAULT '00:00',
    closing_time TEXT NOT NULL DEFAULT '23:59',
    is_24x7 INTEGER NOT NULL DEFAULT 0,
    rating REAL NOT NULL DEFAULT 0,
    rating_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending', -- pending | approved | rejected
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS parking_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parking_id INTEGER NOT NULL REFERENCES parking_facilities(id) ON DELETE CASCADE,
    slot_number TEXT NOT NULL,
    vehicle_type TEXT NOT NULL, -- 2-wheeler | 4-wheeler | ev
    status TEXT NOT NULL DEFAULT 'free', -- free | occupied | reserved | maintenance
    UNIQUE(parking_id, slot_number)
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_ref TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parking_id INTEGER NOT NULL REFERENCES parking_facilities(id) ON DELETE CASCADE,
    slot_id INTEGER REFERENCES parking_slots(id),
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
    booking_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    booking_status TEXT NOT NULL DEFAULT 'confirmed', -- confirmed | cancelled | completed | expired
    amount REAL NOT NULL DEFAULT 0,
    qr_payload TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    transaction_id TEXT UNIQUE NOT NULL,
    amount REAL NOT NULL,
    payment_method TEXT NOT NULL, -- upi | card | netbanking | cash
    payment_status TEXT NOT NULL DEFAULT 'pending', -- pending | success | failed | refunded
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS parking_occupancy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parking_id INTEGER NOT NULL REFERENCES parking_facilities(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    occupied INTEGER NOT NULL,
    available INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    booking_id INTEGER REFERENCES bookings(id),
    type TEXT NOT NULL, -- confirmation | reminder | cancellation | expiry
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'sent',
    sent_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    parking_id INTEGER NOT NULL REFERENCES parking_facilities(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_parking_city ON parking_facilities(city, state);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_parking ON bookings(parking_id);
CREATE INDEX IF NOT EXISTS idx_occupancy_parking_time ON parking_occupancy(parking_id, timestamp);
