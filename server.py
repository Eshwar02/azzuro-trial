"""Local dashboard server; serves only UI assets and a normalized review feed."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
DEMO_FILE = ROOT / "data" / "demo_reviews.json"
sys.path.insert(0, str(ROOT / "src"))

from azzuro_reviews.config import PROPERTY_NAMES, load_dotenv
from azzuro_reviews.insights import annotate_review


def dashboard_payload() -> dict:
    load_dotenv(ROOT / ".env")
    database_path = Path(os.environ.get("AZZURO_DB_PATH", "data/reviews.sqlite3")).expanduser()
    if not database_path.is_absolute():
        database_path = ROOT / database_path
    database_path = database_path.resolve()

    if not database_path.is_file():
        fixture = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
        return {
            "dataset_type": fixture["dataset_type"],
            "notice": fixture["notice"],
            "properties": [
                {"key": key, "name": name} for key, name in PROPERTY_NAMES.items()
            ],
            "last_collected_at": None,
            "last_checked_at": None,
            "collection_runs": [],
            "reviews": [annotate_review(review) for review in fixture["reviews"]],
        }

    connection = sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT property_key, property_id, review_id, review_date, created_timestamp, "
            "last_change_timestamp, language_code, headline, positive_text, negative_text, "
            "rating, sub_scores_json, collected_at FROM reviews "
            "ORDER BY review_date DESC, collected_at DESC"
        ).fetchall()
        reviews = []
        for row in rows:
            review = dict(row)
            review["property_name"] = PROPERTY_NAMES.get(review["property_key"], review["property_key"])
            try:
                review["sub_scores"] = json.loads(review.pop("sub_scores_json") or "{}")
            except json.JSONDecodeError:
                review["sub_scores"] = {}
            reviews.append(annotate_review(review))

        runs = connection.execute(
            "SELECT property_key, property_id, started_at, finished_at, outcome, "
            "reviews_seen, added, updated, unchanged, error_code "
            "FROM collection_runs ORDER BY started_at DESC LIMIT 20"
        ).fetchall()
    finally:
        connection.close()

    return {
        "dataset_type": "booking_api",
        "notice": "Reviews collected through the authorized Booking.com Guest Review API.",
        "properties": [
            {"key": key, "name": name} for key, name in PROPERTY_NAMES.items()
        ],
        "last_collected_at": max((review["collected_at"] for review in reviews if review.get("collected_at")), default=None),
        "last_checked_at": max((run["finished_at"] for run in runs if run["finished_at"]), default=None),
        "collection_runs": [dict(run) for run in runs],
        "reviews": reviews,
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path == "/api/dashboard":
            self._send_dashboard()
            return

        relative = "index.html" if path == "/" else path.lstrip("/")
        asset = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in asset.parents or not asset.is_file():
            self.send_error(404)
            return
        content_type = guess_type(asset.name)[0] or "application/octet-stream"
        body = asset.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") or "javascript" in content_type else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_dashboard(self) -> None:
        try:
            body = json.dumps(dashboard_payload(), ensure_ascii=False).encode("utf-8")
        except (OSError, sqlite3.Error, json.JSONDecodeError, KeyError) as exc:
            print(f"Dashboard data unavailable: {type(exc).__name__}", file=sys.stderr)
            body = json.dumps({"error": "Review data could not be loaded."}).encode("utf-8")
            self.send_response(503)
        else:
            self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        # Avoid logging request query strings, which could contain sensitive data.
        print(f"{self.address_string()} {self.command} {urlsplit(self.path).path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Azzuro review dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: local machine only)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
