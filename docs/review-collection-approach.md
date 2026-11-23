# Review collection approach

## Decision

Use Booking.com's Guest Review API if Azzurro can authorize access for all four properties. Do not build a scraper for the public hotel pages. Booking.com's current terms prohibit automated access, copying, or scraping without its prior express written permission. The public pages also returned a JavaScript/robot-verification screen in this inspection, so they are not a dependable collection source from this environment.

The Guest Review API is documented for internal use by properties. It returns review data to an authorized integration and is a better fit for an operations dashboard than copying content from public pages. This is an access-controlled API, not an open public API: Booking.com says the machine account must have `review-api` permission. The property must be connected to the provider for Guest reviews, and the integration must meet the API's go-live requirements, including a self-assessment and PII compliance.

References:

- [Guest Review API overview](https://developers.booking.com/connectivity/docs/review-api)
- [Retrieve reviews](https://developers.booking.com/connectivity/docs/review-api/retrieve-reviews)
- [Token-based authentication](https://developers.booking.com/connectivity/docs/token-based-authentication)
- [Connectivity API overview and connection types](https://developers.booking.com/connectivity/docs)
- [Guest Review API go-live requirements](https://developers.booking.com/connectivity/docs/going_live)
- [Booking.com Terms and Conditions, section A15](https://www.booking.com/content/terms.html)

## Access check before implementation

Ask the Azzurro Booking.com account owner or current connectivity provider:

1. Are all four listings managed under accounts Azzurro can authorize?
2. Is there already a Booking.com Connectivity Partner or PMS integration with Guest Reviews access?
3. Can that provider grant the review API connection for each property, or can Azzurro authorize a new provider and machine account?
4. What are the four Booking.com hotel IDs, and what review-history start date is available?
5. Can the owner provide test credentials/property access and confirm the permitted internal use and retention of review text?

Do not request or store a personal Extranet password. Use a machine account and tokens supplied through the approved integration process. Keep credentials out of source control and logs.

## Data and sync plan

The documented endpoint retrieves reviews by property ID. Current machine accounts use token-based authentication: exchange the client ID and secret for a short-lived JWT, then call the review endpoint with a bearer token over HTTPS. The response includes a review ID, creation and last-change timestamps, language, positive and negative text where provided, overall and category scores where provided, and metadata. Some fields are optional. The response can also include reviewer details; the dashboard does not need reviewer names, so discard those fields at ingestion.

The API returns ten reviews by default and provides a `next_page` cursor for pagination. The initial sync should follow pages from the approved start date until the API returns an empty page. Booking.com says to keep polling that last empty-page cursor to retrieve the latest modified set. Persist the cursor per property and start date; advance it only after a complete successful run. Upsert by `(property_id, review_id)` and store source timestamps, a validated source URL when present, and the time the collector received each record. Do not treat a failed or partial run as a completed sync.

For each property/run, record start time, finish time, outcome, records seen, added, updated, unchanged, and a safe error code. Retry temporary network, server, and rate-limit failures with bounded backoff. Treat authentication or permission failures as configuration errors requiring attention. Never turn a failed request into an empty review result.

The review API's category scores include cleanliness, facilities, location, services/staff, and value when the guest supplied them. These can complement text-based topic labels; they are not substitutes for mention counts. Preserve the source score scale and missing values.

## If API access is unavailable

First check whether Azzurro's existing PMS or connectivity provider can supply the same reviews through its authorized API or an export it permits for this internal use. Confirm coverage, update cadence, fields, and retention with that provider before integrating it.

If no authorized recurring source is available, do not automate access to Booking.com pages or claim that a partial scrape is reliable. For development, use clearly identified synthetic fixtures or a small dataset supplied by Azzurro through an authorized channel. Label fixture data so it cannot be mistaken for collected reviews. A production collector and real sample data remain blocked until an approved source is available.

## Other sources considered

| Source | What it can provide | Fit for this dashboard |
| --- | --- | --- |
| Booking.com public listing pages | Reviews visible to a normal visitor, subject to page behavior and platform terms. | Not an automated source: Booking.com's terms require prior written permission for automated access. The pages also returned a robot check in our inspection. |
| Booking.com Guest Review API | Structured Booking.com reviews and property scores, with IDs and pagination. | Best fit. Requires an authorized Connectivity machine account and Guest Reviews access for each property. |
| Booking.com reviews iframe | A property view of reviews and replies embedded in a PMS or other interface; iframe URL is short-lived. | Useful as an operational fallback for viewing reviews, but not a structured feed for our own topic counts, weekly trends, and filters. |
| Azzuro's PMS, channel manager, or review-management provider | May already receive Booking.com reviews through an approved connection and may offer an export or API. | Worth checking first with the account owner. Use only if the provider confirms Booking.com coverage, internal-use permission, history, update cadence, and access to review text and IDs. No Azzuro provider or export has been confirmed. |
| Extranet manual export | Booking.com documents viewing reviews in the Extranet. | I found no official documentation confirming a review CSV export. An owner-supplied export is a possible development source only if the account or provider can produce one and confirms its use is allowed. Do not automate the Extranet interface. |
| Google Business Profile Reviews API | Reviews for verified Google Business Profile locations. | Separate review source, not Booking.com data. Could be a future additional channel, but it cannot fill the Booking.com requirement. API access also requires Google approval and an authorized account. |
| Synthetic fixtures | Handwritten examples in the same shape as normalized review records. | Good for building and demonstrating the dashboard while credentials are pending. Must be clearly labeled as synthetic and never presented as collected guest feedback. |

The Booking.com documentation supports the API, connection, and iframe distinctions above. Google documents its API as access to reviews associated with Google Business Profile locations, with project approval required. See [Booking.com's iframe documentation](https://developers.booking.com/connectivity/docs/review-api/access-reviews-iframe), [the Booking.com connection overview](https://developers.booking.com/connectivity/docs), and [Google's review data guide](https://developers.google.com/my-business/content/review-data) and [API access prerequisites](https://developers.google.com/my-business/content/prereqs).

## Findings from this check

- Direct inspection of all four supplied listing URLs returned a JavaScript-disabled robot-verification page in the research browser. This describes this inspection environment; it does not establish whether a normal visitor can view the pages.
- Booking.com's terms page, section A15.2, says automated access, monitoring, copying, scraping, or downloading requires prior express written permission.
- Booking.com documents a Guest Review API for internal property use, with a permissioned machine account and property connection. It is usable only after Azzuro confirms access and completes applicable onboarding/self-assessment requirements.
- The self-assessment tutorial is for existing Connectivity Partners. Its test property has no reviews preloaded: the partner must create a test reservation and submit a test review before exercising retrieval. It is a way to validate an authorized integration, not a source of the four hotels' live reviews.
- No review data was collected in this phase. We have not received Azzuro's property IDs, API permission, credentials, or an authorized export.

## Collector implementation

The repository now has a Python command-line collector in `src/azzuro_reviews/`. It exchanges the machine account credentials for a JWT, caches the token while syncing properties, retries transient failures, follows API pagination links on Booking.com's API host, and upserts reviews and run status into SQLite. It discards reviewer metadata and reservation IDs, and retains a validated source URL when supplied. It follows the API's empty-page cursor between runs; changing the configured start date triggers a fresh backfill.

Run instructions and the environment variable format are in the root [README](../README.md). The collector has not been run against Booking.com because API access and hotel IDs are still unconfirmed. No live review data is included.

The dashboard can continue independently against the normalized review model and explicitly synthetic fixtures. Keep the collector as one data-source adapter; replace the fixtures with API records when access is confirmed. Live source access remains important for final data accuracy and the sample-data deliverable, but it does not need to block layout, filters, trend calculations, or topic-classifier work.

## Phase 2 outcome

Collection method selected: the authorized Guest Review API, subject to access confirmation. Scraping is rejected. The collector is implemented, but live collection and real sample data require the access check above. Until then, local dashboard work should use labeled fixtures rather than real guest reviews.
