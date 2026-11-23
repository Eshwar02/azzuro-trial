"""SQLite persistence for reviews and per-property collection runs."""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


REVIEW_FIELDS = (
    "created_timestamp", "last_change_timestamp", "review_date", "language_code",
    "headline", "positive_text", "negative_text", "rating", "sub_scores_json", "source_url",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ReviewStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                property_key TEXT NOT NULL,
                property_id TEXT NOT NULL,
                review_id TEXT NOT NULL,
                created_timestamp TEXT,
                last_change_timestamp TEXT,
                review_date TEXT,
                language_code TEXT,
                headline TEXT,
                positive_text TEXT,
                negative_text TEXT,
                rating REAL,
                sub_scores_json TEXT NOT NULL DEFAULT '{}',
                source_url TEXT,
                collected_at TEXT NOT NULL,
                PRIMARY KEY (property_id, review_id)
            );

            CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(review_date);
            CREATE INDEX IF NOT EXISTS idx_reviews_property_date
                ON reviews(property_key, review_date);

            CREATE TABLE IF NOT EXISTS collection_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_key TEXT NOT NULL,
                property_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                outcome TEXT NOT NULL,
                reviews_seen INTEGER NOT NULL DEFAULT 0,
                added INTEGER NOT NULL DEFAULT 0,
                updated INTEGER NOT NULL DEFAULT 0,
                unchanged INTEGER NOT NULL DEFAULT 0,
                error_code TEXT
            );

            CREATE TABLE IF NOT EXISTS sync_state (
                property_id TEXT PRIMARY KEY,
                from_date TEXT NOT NULL,
                poll_url TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        review_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(reviews)")
        }
        if "source_url" not in review_columns:
            self.connection.execute("ALTER TABLE reviews ADD COLUMN source_url TEXT")
        self.connection.commit()

    def start_run(self, property_key: str, property_id: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO collection_runs (property_key, property_id, started_at, outcome) "
            "VALUES (?, ?, ?, 'running')",
            (property_key, property_id, utc_now()),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def save_review(self, property_key: str, property_id: str, source: dict) -> str:
        review_id = source.get("review_id")
        if not isinstance(review_id, (str, int)) or not str(review_id).strip():
            raise ValueError("Review is missing a valid review_id")
        content = source.get("content") if isinstance(source.get("content"), dict) else {}
        scoring = source.get("scoring") if isinstance(source.get("scoring"), dict) else {}
        created = self._string(source.get("created_timestamp"))
        scores = {
            key: value for key, value in scoring.items()
            if key != "review_score" and isinstance(value, (str, int, float, type(None)))
            and not isinstance(value, bool)
        }
        review = {
            "created_timestamp": created,
            "last_change_timestamp": self._string(source.get("last_change_timestamp")),
            "review_date": created[:10] if created else None,
            "language_code": self._string(content.get("language_code")),
            "headline": self._string(content.get("headline")),
            "positive_text": self._string(content.get("positive")),
            "negative_text": self._string(content.get("negative")),
            "rating": self._number(scoring.get("review_score")),
            "sub_scores_json": json.dumps(scores, ensure_ascii=False, sort_keys=True),
            "source_url": self._safe_source_url(source.get("url")),
        }
        existing = self.connection.execute(
            "SELECT " + ", ".join(REVIEW_FIELDS) +
            " FROM reviews WHERE property_id = ? AND review_id = ?",
            (property_id, str(review_id)),
        ).fetchone()
        values = tuple(review[field] for field in REVIEW_FIELDS)
        if existing is None:
            self.connection.execute(
                "INSERT INTO reviews (property_key, property_id, review_id, "
                + ", ".join(REVIEW_FIELDS) + ", collected_at) VALUES ("
                + ", ".join("?" for _ in range(3 + len(REVIEW_FIELDS) + 1)) + ")",
                (property_key, property_id, str(review_id), *values, utc_now()),
            )
            return "added"
        if tuple(existing[field] for field in REVIEW_FIELDS) == values:
            return "unchanged"
        assignments = ", ".join(f"{field} = ?" for field in REVIEW_FIELDS)
        self.connection.execute(
            f"UPDATE reviews SET {assignments}, collected_at = ? "
            "WHERE property_id = ? AND review_id = ?",
            (*values, utc_now(), property_id, str(review_id)),
        )
        return "updated"

    def get_poll_url(self, property_id: str, from_date: str) -> str | None:
        row = self.connection.execute(
            "SELECT poll_url FROM sync_state WHERE property_id = ? AND from_date = ?",
            (property_id, from_date),
        ).fetchone()
        return row["poll_url"] if row else None

    def save_poll_url(self, property_id: str, from_date: str, poll_url: str) -> None:
        self.connection.execute(
            "INSERT INTO sync_state (property_id, from_date, poll_url, updated_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(property_id) DO UPDATE SET "
            "from_date = excluded.from_date, poll_url = excluded.poll_url, updated_at = excluded.updated_at",
            (property_id, from_date, poll_url, utc_now()),
        )
        self.connection.commit()

    def finish_run(self, run_id: int, outcome: str, counts: dict[str, int], error_code: str | None = None) -> None:
        self.connection.execute(
            "UPDATE collection_runs SET finished_at = ?, outcome = ?, reviews_seen = ?, "
            "added = ?, updated = ?, unchanged = ?, error_code = ? WHERE run_id = ?",
            (utc_now(), outcome, counts["seen"], counts["added"], counts["updated"],
             counts["unchanged"], error_code, run_id),
        )
        self.connection.commit()

    def commit(self) -> None:
        self.connection.commit()

    @staticmethod
    def _string(value: object) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _number(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Review score is not finite")
        return result

    @staticmethod
    def _safe_source_url(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        parsed = urlparse(value)
        if parsed.scheme == "https" and parsed.hostname == "supply-xml.booking.com":
            return value
        return None
