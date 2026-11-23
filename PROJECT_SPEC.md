# Review dashboard: first release

## What this is for

The dashboard is for the Azzurro operations team. It should make it easy to see how guests rate each property, spot recurring complaints, and open the reviews behind a trend. Reviews can point to areas that need attention; they do not, by themselves, prove what caused a problem.

The first release covers these Booking.com listings:

| Property | Listing |
| --- | --- |
| Olympic Hotel Paddington | [Booking.com](https://www.booking.com/hotel/au/olympic-paddington.html) |
| Potts Point | [Booking.com](https://www.booking.com/hotel/au/venus-potts-point-sydney.html) |
| Central Sydney | [Booking.com](https://www.booking.com/hotel/au/venus-surry-hills.html) |
| Darling Harbour | [Booking.com](https://www.booking.com/hotel/au/chateau-de-venus.html) |

## First release

The app will collect the publicly available review information it can access for these listings, keep a deduplicated local dataset, and show:

- Average overall rating this week and the change from the comparable period last week.
- Rating and review count for each property.
- A review list with date, property, rating, sentiment, and topic labels.
- Date and property filters that apply to all dashboard figures and lists.
- Positive and negative review trends, plus common operational topics.
- Collection freshness and any property-level collection errors.

User accounts, notifications, review replies, forecasts, and live monitoring are outside this first release. The initial result will be a local demo unless deployment is separately arranged.

## Review records

Each record should include the following where the source provides it:

| Field | Handling |
| --- | --- |
| Property ID and display name | Required; use a fixed mapping for the four listings. |
| Overall rating | Required for rating summaries. Keep the source value and scale. |
| Review date | Required for time-based views. Keep the displayed source date and a normalized date. |
| Review text | Preserve original wording. Keep positive and negative text separate if the source does. |
| Source review ID | Save when available; use it to recognize an existing review. |
| Source reference | Keep a public review or listing reference when available for traceability. |
| Collected-at time | Required; record when the collector first saw the review and when it last checked it. |
| Stay date, language, trip type, room details | Keep only when public, useful, and consistently available. |

Reviewer names are not needed for operations reporting and should not be collected. Missing source fields stay missing; the app must not infer or fabricate them. An edited review with the same source ID updates the existing record.

## Reporting rules

- Use the source's overall rating for headline averages. Preserve its original scale. If ratings from different scales ever need to be combined, convert them explicitly and document the conversion.
- A week runs Monday 00:00 to the next Monday 00:00 in `Australia/Sydney` time.
- “This week” means the current week so far. Compare it with the same elapsed days of the previous week, and label that comparison clearly in the dashboard.
- Show review counts next to averages and changes. A small sample should be visible as a small sample.
- If a period has no reviews, show “No reviews” and no percentage change. Do not show zero as if it were a rating.
- Positive and negative trend counts use the review's publication date and the currently selected filters.

## Sentiment and topics

Each review can be labelled positive, mixed/neutral, or negative. Rating can help classify sentiment, but text and rating may disagree; keep those cases visible for review rather than treating the score as a perfect reading of the text.

Initial topic labels:

- Cleanliness
- Check-in
- Staff and reception
- Noise
- Facilities
- Location
- Room condition
- Value for money

A review may have more than one topic, or none. Topic summaries must link back to the reviews they count. For example, “40% of negative reviews mentioned cleanliness” means cleanliness-tagged negative reviews divided by all negative reviews in the selected period. Show the count as well as the percentage.

The first classifier should favor rules that can be explained and checked. Keep unclassified reviews available. Keyword rules can miss context, sarcasm, spelling variations, and other languages, so topic and sentiment labels are signals for staff to inspect, not definitive judgments.

## Collection and data quality

The collector must use an authorized source and must not depend on a staff member's login, personal cookies, or credentials. Phase 2 selected Booking.com's internal Guest Review API, subject to Azzurro confirming property access, a permitted connection, and machine-account permissions. Scraping the public pages is out of scope without Booking.com's prior express written permission. See [the collection approach](docs/review-collection-approach.md) for the access check and fallback plan.

Each run should report its start and finish time and a result for each property. Distinguish a successful check with no new reviews from a failed or partial check. Temporary failures should be retryable and must not remove previously collected records. Track reviews added, updated, skipped as duplicates, and any errors.

Use a source ID for deduplication when available. Otherwise, use a documented fingerprint based on stable review details, scoped to the property. Validate required fields, rating ranges, dates, and property mapping before records reach dashboard summaries. Keep enough source and run information to investigate bad data. If a page changes or a field cannot be read, report that clearly rather than silently treating it as an empty result.

## Dashboard behavior

Open on all four properties and the current week. Date and property filters must update headline figures, property comparisons, trends, topic summaries, and the review list together. Sort reviews newest first by default. Each review should show enough context to interpret it, and every insight should lead to the reviews behind it.

Show when data was last checked. Make loading, no-review, stale-data, and collection-error states understandable to a non-technical user. Use plain labels and pair percentages with counts.

## Working assumptions

- Sydney local time is the reporting timezone because all four properties are in Sydney.
- The comparison is week-to-date against the same elapsed portion of the prior week.
- Initial history includes as much accessible public review data as the chosen method can collect reliably; the actual coverage will be stated in the README.
- Include only review text and metadata actually exposed by the selected collection method. Language handling will be documented once source data has been inspected.
- A local demo is sufficient for the trial unless a hosted demo is requested.
- Booking.com page structure and access can change. The collection method, permitted use, and practical limits must be checked before implementation and explained in the final documentation.
