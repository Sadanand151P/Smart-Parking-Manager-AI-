"""
QR ticket service.

The `qrcode` package (and its zbar/PIL decode counterparts) isn't installable
in this offline sandbox, so this module does two things:

1. build_qr_payload() — always available, no dependency. Produces the exact
   JSON string that should be encoded into the QR (booking ref, vehicle,
   slot, validity window). This is what actually matters for entry/exit
   scanning logic and the ML/booking pipeline.
2. render_qr_placeholder() — draws a scannable-*looking* module grid with
   Pillow so the ticket UI has something to show locally. In the real
   deployment, replace its body with:
       import qrcode
       img = qrcode.make(payload_json)
   which is a one-line swap — nothing else in the app needs to change since
   callers only use build_qr_payload() for logic and treat the image as an
   opaque PNG.
"""

import json
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QR_OUTPUT_DIR = os.path.join(BASE_DIR, "data", "qr_tickets")


def build_qr_payload(booking_ref, vehicle_number, parking_name, slot_number, start_time, end_time) -> str:
    payload = {
        "booking_ref": booking_ref,
        "vehicle": vehicle_number,
        "parking": parking_name,
        "slot": slot_number,
        "valid_from": start_time,
        "valid_to": end_time,
    }
    return json.dumps(payload, separators=(",", ":"))


def render_qr_placeholder(payload: str, booking_ref: str, modules: int = 25, module_px: int = 10) -> str:
    """Deterministic module grid derived from a SHA-256 hash of the payload.
    NOT a real, decodable QR code — visual stand-in only. See module docstring."""
    try:
        from PIL import Image, ImageDraw  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required to render QR ticket images; install it with 'pip install Pillow'"
        ) from exc

    os.makedirs(QR_OUTPUT_DIR, exist_ok=True)
    digest = hashlib.sha256(payload.encode()).digest()
    bits = []
    for byte in digest:
        bits.extend([(byte >> i) & 1 for i in range(8)])
    while len(bits) < modules * modules:
        bits.extend(bits)
    bits = bits[: modules * modules]

    size = modules * module_px
    img = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(img)
    for row in range(modules):
        for col in range(modules):
            if bits[row * modules + col]:
                x0, y0 = col * module_px, row * module_px
                draw.rectangle([x0, y0, x0 + module_px, y0 + module_px], fill="black")

    # Draw finder-pattern-style corner squares so it visually reads as a QR code.
    def finder(top_left_col, top_left_row):
        x0, y0 = top_left_col * module_px, top_left_row * module_px
        draw.rectangle([x0, y0, x0 + 7 * module_px, y0 + 7 * module_px], fill="black")
        draw.rectangle([x0 + module_px, y0 + module_px, x0 + 6 * module_px, y0 + 6 * module_px], fill="white")
        draw.rectangle([x0 + 2 * module_px, y0 + 2 * module_px, x0 + 5 * module_px, y0 + 5 * module_px], fill="black")

    finder(0, 0)
    finder(modules - 7, 0)
    finder(0, modules - 7)

    out_path = os.path.join(QR_OUTPUT_DIR, f"{booking_ref}.png")
    img.save(out_path)
    return out_path
