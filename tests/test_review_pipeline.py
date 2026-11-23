from __future__ import annotations

import os
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen
from zoneinfo import ZoneInfo
from http.server import ThreadingHTTPServer
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from azzuro_reviews.booking import BookingAPIError, BookingClient
from azzuro_reviews.store import ReviewStore
from server import DashboardHandler, dashboard_payload


def source_review(**overrides: object) -> dict:
    review = {
        "review_id": "review-1",
        "created_timestamp": "2026-06-12 10:30:00",
        "last_change_timestamp": "2026-06-13 10:30:00",
        "content": {
            "language_code": "en-gb",
            "headline": "A pleasant stay",
            "positive": "The staff were helpful.",
            "negative": "",
        },
        "scoring": {"review_score": 8.5, "cleanliness": 9, "location": 7},
    }
    review.update(overrides)
    return review


class ReviewStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = ReviewStore(Path(self.temp.name) / "reviews.sqlite3")

    def tearDown(self) -> None:
        self.store.close()
        self.temp.cleanup()

    def test_upsert_is_idempotent_and_updates_edited_review(self) -> None:
        record = source_review()
        self.assertEqual(self.store.save_review("potts-point", "123", record), "added")
        self.assertEqual(self.store.save_review("potts-point", "123", record), "unchanged")
        record["content"]["positive"] = "The receptionist was excellent."
        self.assertEqual(self.store.save_review("potts-point", "123", record), "updated")
        saved = self.store.connection.execute(
            "SELECT COUNT(*) AS count, positive_text FROM reviews"
        ).fetchone()
        self.assertEqual(saved["count"], 1)
        self.assertEqual(saved["positive_text"], "The receptionist was excellent.")

    def test_invalid_overall_score_or_timestamp_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "1 to 10"):
            self.store.save_review(
                "potts-point", "123", source_review(scoring={"review_score": 11})
            )
        with self.assertRaisesRegex(ValueError, "created_timestamp"):
            self.store.save_review(
                "potts-point", "123", source_review(created_timestamp="not-a-date")
            )

    def test_malformed_optional_subscores_are_discarded(self) -> None:
        record = source_review(scoring={
            "review_score": 8,
            "cleanliness": 9,
            "facilities": 15,
            "location": float("nan"),
            "staff": "unknown",
        })
        self.store.save_review("potts-point", "123", record)
        saved = self.store.connection.execute(
            "SELECT sub_scores_json FROM reviews"
        ).fetchone()
        self.assertEqual(saved["sub_scores_json"], '{"cleanliness": 9.0}')


class BookingClientTests(unittest.TestCase):
    def test_follows_cursor_and_saves_only_the_empty_page_cursor(self) -> None:
        client = BookingClient("id", "secret")
        first_url = "https://supply-xml.booking.com/reviews/properties/123/reviews?cursor=next"
        pages = [
            {"data": {"reviews": [source_review()]}, "meta": {"next_page": first_url}},
            {"data": {"reviews": []}, "meta": {}},
        ]
        with patch.object(client, "_request_json", side_effect=pages) as request:
            reviews = list(client.reviews("123", "2026-01-01"))
        self.assertEqual(len(reviews), 1)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(client.last_poll_url, first_url)

    def test_nonempty_page_without_cursor_fails_without_advancing_checkpoint(self) -> None:
        client = BookingClient("id", "secret")
        with patch.object(client, "_request_json", return_value={
            "data": {"reviews": [source_review()]}, "meta": {},
        }):
            with self.assertRaisesRegex(BookingAPIError, "next-page cursor"):
                list(client.reviews("123", "2026-01-01"))
        self.assertIsNone(client.last_poll_url)

    def test_cursor_cannot_escape_the_review_endpoint(self) -> None:
        client = BookingClient("id", "secret")
        with patch.object(client, "_request_json") as request:
            with self.assertRaisesRegex(BookingAPIError, "unexpected review pagination"):
                list(client.reviews("123", "2026-01-01", "https://example.com/reviews"))
        request.assert_not_called()


class DashboardPayloadTests(unittest.TestCase):
    def test_demo_payload_is_explicit_and_uses_current_relative_dates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "not-created.sqlite3"
            with patch.dict(os.environ, {"AZZURO_DB_PATH": str(database)}):
                payload = dashboard_payload()
        self.assertEqual(payload["dataset_type"], "synthetic_demo_not_collected")
        self.assertEqual(len(payload["reviews"]), 12)
        today = datetime.now(ZoneInfo("Australia/Sydney")).date().isoformat()
        self.assertEqual(payload["reviews"][0]["review_date"], today)
        self.assertTrue(all(review["is_synthetic"] for review in payload["reviews"]))


class DashboardHTTPIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.env = patch.dict(os.environ, {
            "AZZURO_DB_PATH": str(Path(cls.temp.name) / "not-created.sqlite3"),
        })
        cls.env.start()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
        cls.thread = Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)
        cls.env.stop()
        cls.temp.cleanup()

    def test_page_assets_and_dashboard_api_serve_expected_content(self) -> None:
        with urlopen(self.base_url + "/", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"Guest feedback", response.read())
        with urlopen(self.base_url + "/app.js", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"function updateSummary", response.read())
        with urlopen(self.base_url + "/api/dashboard", timeout=3) as response:
            payload = json.load(response)
        self.assertEqual(payload["dataset_type"], "synthetic_demo_not_collected")
        self.assertEqual(len(payload["reviews"]), 12)
        with self.assertRaises(HTTPError) as failure:
            urlopen(self.base_url + "/does-not-exist", timeout=3)
        self.assertEqual(failure.exception.code, 404)
        failure.exception.close()


if __name__ == "__main__":
    unittest.main()
