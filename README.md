# Azzuro Review Insights

The collector is designed for Booking.com's authorized Guest Review API and writes review data to a local SQLite database. Rule-based sentiment and topic helpers are also in place for dashboard work. The app does not scrape the public hotel pages.

## Requirements

- Python 3.10 or newer.
- A Booking.com Connectivity machine account using token-based authentication.
- `review-api` access for all four properties, with the Guest reviews connection enabled.
- The Booking.com hotel ID for each property.

The API is for internal property use. Azzuro must confirm that its account and intended use are authorized before collecting real reviews. See [the collection approach](docs/review-collection-approach.md) for the access requirements and limits.

## Configure

```sh
cp .env.example .env
```

Edit `.env` with the machine account's client ID and secret and the four hotel IDs. Keep `.env` private; it is ignored by Git. Do not put credentials in command arguments, screenshots, logs, or source files.

The property keys are `olympic-paddington`, `potts-point`, `central-sydney`, and `darling-harbour`. The collector rejects missing keys, non-numeric IDs, and duplicate IDs before making API requests.

## Run a sync

From the repository root:

```sh
PYTHONPATH=src python3 -m azzuro_reviews sync --from-date 2024-01-01
```

`--from-date` is inclusive. Choose a start date Azzuro is authorized to retain. The first run reads pages from that date until Booking.com returns an empty page. Later runs resume from the saved empty-page cursor, following new pages until the next empty page. Reviews are upserted by `(property_id, review_id)`, so repeats and edited reviews do not create duplicates. Changing `--from-date` starts a fresh backfill. The collector processes properties one at a time and exits non-zero if any property fails.

By default, records go to `data/reviews.sqlite3`. Set `AZZURO_DB_PATH` in `.env` to use another path. No third-party Python packages are required.

## Stored data

The `reviews` table stores property identifiers, review IDs, source timestamps, date, language, headline, positive and negative text, overall score, available category scores, a validated Booking.com source URL when supplied, and collection time. Reviewer details, replies, and reservation IDs are discarded during ingestion. Some reviews contain a score but no text; those records remain available for rating summaries and are labelled as having no written comment.

The `collection_runs` table records each property's run status, counts, start and finish times, and a non-sensitive error code. A failed API call is recorded as a failure, not as a successful empty result. Some records may have been saved before a later page failed; the run record makes that partial outcome visible, and a later sync safely revisits the same reviews.

## Insights and demo data

`src/azzuro_reviews/insights.py` adds explainable sentiment and topic labels. The dashboard calculates its summaries from the currently selected date and property filters. When both positive and negative text are present, sentiment is mixed. Otherwise the text decides; a score of 8 or more is positive, 5 or less negative, and scores between them mixed when no text is available. Topic labels use English keyword patterns and can overlap. A topic percentage divides reviews with that topic by all reviews in the selected sentiment group. A strong disagreement between text and rating is flagged for a human check.

`data/demo_reviews.json` contains fictional sample records to support dashboard development. Its dates are relative to the current Sydney date so the weekly view stays populated over time. The file is marked `synthetic_demo_not_collected`; these are not Booking.com reviews and must be shown as demo data in any interface. Replace them with authorized API records when access is confirmed.

## Open the dashboard

From the repository root, run:

```sh
python3 server.py
```

Then open `http://127.0.0.1:8000`. The server binds to the local machine by default. It reads from the configured SQLite database when one exists; until then, it uses the clearly marked synthetic demo file. It serves only the dashboard assets and the normalized dashboard response, not repository files or `.env`.

The source timestamp is retained as returned. The API documentation's example does not specify a timezone for its timestamp string, so `review_date` currently uses its date portion. Confirm timestamp semantics before using hour-level reporting or converting dates across timezones.

## Reliability and known limits

- The collector uses Booking.com's documented token exchange endpoint. Tokens expire after one hour; an expired token gets one refresh and retry.
- Transient network, timeout, rate-limit, and server errors are retried a limited number of times. Authentication, permission, malformed response, and other request errors fail the property's run.
- Pagination links are followed only over HTTPS on `supply-xml.booking.com`; repeated links are treated as an error.
- The collector stores the API's empty-page cursor per property and start date. Booking.com documents polling that cursor to receive the latest modified reviews. A changed start date triggers a backfill; failed runs do not advance the saved cursor.
- Fields and category scores are optional. Missing values stay empty. Reviewer names and other unnecessary reviewer metadata are not retained.
- No credentials, production property IDs, or real review data are included in this repository. Live collection has not been run because Azzuro has not supplied authorized API access.

## Project notes

- [Phase 1 scope and reporting rules](PROJECT_SPEC.md)
- [Collection method and access check](docs/review-collection-approach.md)
