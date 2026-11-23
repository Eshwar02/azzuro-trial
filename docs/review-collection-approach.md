# Review collection approach

## Decision

Use Booking.com's Guest Review API if Azzurro can authorize access for all four properties. Do not build a scraper for the public hotel pages. Booking.com's current terms prohibit automated access, copying, or scraping without its prior express written permission. The public pages also returned a JavaScript/robot-verification screen in this inspection, so they are not a dependable collection source from this environment.

The Guest Review API is documented for internal use by properties. It returns review data to an authorized integration and is a better fit for an operations dashboard than copying content from public pages. This is an access-controlled API, not an open public API: Booking.com says the machine account must have `review-api` permission. The property must be connected to the provider for Guest reviews, and the integration must meet the API's go-live requirements, including a self-assessment and PII compliance.

References:

- [Guest Review API overview](https://developers.booking.com/connectivity/docs/review-api)
- [Retrieve reviews](https://developers.booking.com/connectivity/docs/review-api/retrieve-reviews)
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

The documented endpoint retrieves reviews by property ID. Requests use a bearer JWT over HTTPS. The response includes a review ID, creation and last-change timestamps, language, positive and negative text where provided, overall and category scores where provided, and metadata. Some fields are optional. The response can also include reviewer details; the dashboard does not need reviewer names, so discard those fields at ingestion.

The API returns ten reviews by default and provides a `next_page` cursor for pagination. The initial sync should follow pages from the approved start date until the API returns an empty page. Scheduled syncs should follow the API's pagination guidance to reach the latest modified reviews and upsert by `(property_id, review_id)`. Store the source timestamps and the time the collector received each record. Keep the last successful cursor/checkpoint per property. Do not advance a checkpoint after a failed or partial run.

For each property/run, record start time, finish time, outcome, pages read, records added or updated, duplicates skipped, and error details. Retry temporary network, server, and rate-limit failures with bounded backoff. Treat authentication or permission failures as configuration errors requiring attention. Never turn a failed request into an empty review result.

The review API's category scores include cleanliness, facilities, location, services/staff, and value when the guest supplied them. These can complement text-based topic labels; they are not substitutes for mention counts. Preserve the source score scale and missing values.

## If API access is unavailable

First check whether Azzurro's existing PMS or connectivity provider can supply the same reviews through its authorized API or an export it permits for this internal use. Confirm coverage, update cadence, fields, and retention with that provider before integrating it.

If no authorized recurring source is available, do not automate access to Booking.com pages or claim that a partial scrape is reliable. For development, use clearly identified synthetic fixtures or a small dataset supplied by Azzurro through an authorized channel. Label fixture data so it cannot be mistaken for collected reviews. A production collector and real sample data remain blocked until an approved source is available.

## Findings from this check

- Direct inspection of all four supplied listing URLs returned a JavaScript-disabled robot-verification page in the research browser. This describes this inspection environment; it does not establish whether a normal visitor can view the pages.
- Booking.com's terms page, section A15.2, says automated access, monitoring, copying, scraping, or downloading requires prior express written permission.
- Booking.com documents a Guest Review API for internal property use, with a permissioned machine account and property connection. It is usable only after Azzuro confirms access and completes applicable onboarding/self-assessment requirements.
- No review data was collected in this phase. We have not received Azzuro's property IDs, API permission, credentials, or an authorized export.

## Phase 2 outcome

Collection method selected: the authorized Guest Review API, subject to access confirmation. Scraping is rejected. The next implementation step depends on the access check above; until then, build against labeled fixtures rather than real guest reviews.
