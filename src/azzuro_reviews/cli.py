"""Command-line entry point for authorized review collection."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date

from .booking import BookingAPIError, BookingClient
from .config import PROPERTY_NAMES, load_config
from .store import ReviewStore


DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect reviews through Booking.com's authorized Guest Review API.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync = subparsers.add_parser("sync", help="Fetch reviews from an inclusive start date and upsert them locally")
    sync.add_argument("--from-date", required=True, help="Inclusive start date in YYYY-MM-DD format")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not DATE_PATTERN.fullmatch(args.from_date):
        print("--from-date must use YYYY-MM-DD format", file=sys.stderr)
        return 2
    try:
        date.fromisoformat(args.from_date)
        config = load_config()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    store = ReviewStore(config.database_path)
    client = BookingClient(config.client_id, config.client_secret)
    failures = 0
    try:
        for property_key in PROPERTY_NAMES:
            property_id = config.properties[property_key]
            run_id = store.start_run(property_key, property_id)
            counts = {"seen": 0, "added": 0, "updated": 0, "unchanged": 0}
            try:
                for source_review in client.reviews(property_id, args.from_date):
                    counts["seen"] += 1
                    result = store.save_review(property_key, property_id, source_review)
                    counts[result] += 1
                store.commit()
                store.finish_run(run_id, "success", counts)
                print(
                    f"{PROPERTY_NAMES[property_key]}: success; {counts['seen']} seen, "
                    f"{counts['added']} added, {counts['updated']} updated, "
                    f"{counts['unchanged']} unchanged"
                )
            except (BookingAPIError, ValueError) as exc:
                store.commit()
                code = str(exc.status_code) if isinstance(exc, BookingAPIError) and exc.status_code else type(exc).__name__
                store.finish_run(run_id, "failed", counts, code)
                failures += 1
                print(f"{PROPERTY_NAMES[property_key]}: failed ({code}): {exc}", file=sys.stderr)
    finally:
        store.close()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
