"""Configuration loading and validation for the review collector."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


PROPERTY_NAMES = {
    "olympic-paddington": "Olympic Hotel Paddington",
    "potts-point": "Potts Point",
    "central-sydney": "Central Sydney",
    "darling-harbour": "Darling Harbour",
}


@dataclass(frozen=True)
class CollectorConfig:
    client_id: str
    client_secret: str
    properties: dict[str, str]
    database_path: Path


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE entries without overriding the process environment."""
    if not path.is_file():
        return

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid .env entry on line {line_number}; expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def load_config() -> CollectorConfig:
    load_dotenv()
    client_id = os.environ.get("BOOKING_CLIENT_ID", "").strip()
    client_secret = os.environ.get("BOOKING_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ValueError("Set BOOKING_CLIENT_ID and BOOKING_CLIENT_SECRET in .env or the environment")

    raw_properties = os.environ.get("BOOKING_PROPERTY_IDS", "")
    if not raw_properties:
        raise ValueError("Set BOOKING_PROPERTY_IDS to a JSON object of property keys and hotel IDs")
    try:
        properties = json.loads(raw_properties)
    except json.JSONDecodeError as exc:
        raise ValueError("BOOKING_PROPERTY_IDS must be valid JSON") from exc
    if not isinstance(properties, dict):
        raise ValueError("BOOKING_PROPERTY_IDS must be a JSON object")

    missing = sorted(set(PROPERTY_NAMES) - set(properties))
    extra = sorted(set(properties) - set(PROPERTY_NAMES))
    if missing or extra:
        details = []
        if missing:
            details.append("missing keys: " + ", ".join(missing))
        if extra:
            details.append("unknown keys: " + ", ".join(extra))
        raise ValueError("BOOKING_PROPERTY_IDS has " + "; ".join(details))

    normalized: dict[str, str] = {}
    for key, value in properties.items():
        hotel_id = str(value).strip()
        if not hotel_id.isdigit():
            raise ValueError(f"Hotel ID for {key} must contain digits only")
        normalized[key] = hotel_id
    if len(set(normalized.values())) != len(normalized):
        raise ValueError("Each property must have a distinct Booking.com hotel ID")

    database_path = Path(os.environ.get("AZZURO_DB_PATH", "data/reviews.sqlite3")).expanduser()
    return CollectorConfig(client_id, client_secret, normalized, database_path)
