import re

MOBILE_RE = re.compile(r"^[6-9]\d{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Indian vehicle registration: SS NN LL NNNN  (e.g. UP32NR7783), some variants
# use 1-2 letter series and 1-4 digit numbers.
VEHICLE_RE = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{1,4}$")
PINCODE_RE = re.compile(r"^\d{6}$")


def is_valid_mobile(mobile: str) -> bool:
    mobile = mobile.strip().replace(" ", "").replace("+91", "")
    return bool(MOBILE_RE.match(mobile))


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip()))


def normalize_vehicle_number(raw: str) -> str:
    return re.sub(r"[\s\-]", "", raw.strip().upper())


def is_valid_vehicle_number(raw: str) -> bool:
    return bool(VEHICLE_RE.match(normalize_vehicle_number(raw)))


def is_valid_pincode(pincode: str) -> bool:
    return bool(PINCODE_RE.match(pincode.strip()))


def sanitize_str(value: str, max_len: int = 255) -> str:
    if value is None:
        return ""
    return str(value).strip()[:max_len]
