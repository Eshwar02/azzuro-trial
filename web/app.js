const TOPIC_LABELS = {
  cleanliness: "Cleanliness",
  check_in: "Check-in",
  staff: "Staff and reception",
  noise: "Noise",
  facilities: "Facilities",
  location: "Location",
  room_condition: "Room condition",
  value_for_money: "Value for money",
};

const state = { payload: null, reviews: [], propertyNames: new Map() };

function sydneyToday() {
  const parts = new Intl.DateTimeFormat("en-AU", {
    timeZone: "Australia/Sydney",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function shiftDate(value, days) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function firstDayOfWeek(value) {
  const date = new Date(`${value}T12:00:00Z`);
  const weekday = (date.getUTCDay() + 6) % 7;
  return shiftDate(value, -weekday);
}

function defaultWeek() {
  const today = sydneyToday();
  document.querySelector("#date-from").value = firstDayOfWeek(today);
  document.querySelector("#date-to").value = today;
}

function currentFilters() {
  return {
    property: document.querySelector("#property-filter").value,
    from: document.querySelector("#date-from").value,
    to: document.querySelector("#date-to").value,
  };
}

function selectedReviews(filters = currentFilters()) {
  if (!filters.from || !filters.to || filters.from > filters.to) return [];
  return state.reviews.filter((review) => {
    const propertyMatches = filters.property === "all" || review.property_key === filters.property;
    return propertyMatches && review.review_date >= filters.from && review.review_date <= filters.to;
  });
}

function rangeLabel(from, to) {
  if (!from || !to) return "Choose a date range";
  return `${formatDate(from)} – ${formatDate(to)}`;
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-AU", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(`${value}T12:00:00Z`));
}

function formatShortDate(value) {
  return new Intl.DateTimeFormat("en-AU", { day: "numeric", month: "short", timeZone: "UTC" })
    .format(new Date(`${value}T12:00:00Z`));
}

function average(reviews) {
  const scores = reviews.map((review) => ratingValue(review.rating)).filter((score) => score !== null);
  return scores.length ? scores.reduce((total, score) => total + score, 0) / scores.length : null;
}

function ratingValue(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function updateSummary(reviews, filters) {
  if (!filters.from || !filters.to || filters.from > filters.to) {
    document.querySelector("#average-rating").textContent = "—";
    document.querySelector("#rating-change").textContent = "Set a valid date range";
    document.querySelector("#review-count").innerHTML = "<strong>0</strong>";
    document.querySelector("#range-label").textContent = "Selected dates";
    document.querySelector("#negative-count").textContent = "0";
    document.querySelector("#negative-share").textContent = "";
    document.querySelector("#top-topic").innerHTML = "<strong>—</strong>";
    document.querySelector("#top-topic-detail").textContent = "Choose a valid date range";
    return;
  }
  const start = filters.from;
  const end = filters.to;
  const days = Math.round((new Date(`${end}T12:00:00Z`) - new Date(`${start}T12:00:00Z`)) / 86400000) + 1;
  const previousStart = shiftDate(start, -days);
  const previousEnd = shiftDate(start, -1);
  const property = filters.property;
  const previousReviews = state.reviews.filter((review) =>
    (property === "all" || review.property_key === property) &&
    review.review_date >= previousStart && review.review_date <= previousEnd
  );
  const currentAverage = average(reviews);
  const previousAverage = average(previousReviews);
  document.querySelector("#average-rating").textContent = currentAverage === null ? "—" : currentAverage.toFixed(1);
  const change = document.querySelector("#rating-change");
  if (currentAverage === null || previousAverage === null) {
    change.textContent = previousAverage === null ? "No reviews in comparison period" : "No reviews in selected period";
    change.className = "metric-foot";
  } else {
    const delta = currentAverage - previousAverage;
    change.textContent = `${delta > 0 ? "+" : ""}${delta.toFixed(1)} points vs previous period`;
    change.className = `metric-foot ${delta > 0 ? "change-positive" : delta < 0 ? "change-negative" : ""}`;
  }
  document.querySelector("#review-count").innerHTML = `<strong>${reviews.length}</strong>`;
  document.querySelector("#range-label").textContent = rangeLabel(start, end);

  const negative = reviews.filter((review) => review.sentiment === "negative");
  const negativeShare = reviews.length ? Math.round((negative.length / reviews.length) * 100) : 0;
  document.querySelector("#negative-count").textContent = String(negative.length);
  document.querySelector("#negative-share").textContent = reviews.length ? `${negativeShare}% of reviews` : "";

  const topicCounts = new Map(Object.keys(TOPIC_LABELS).map((topic) => [topic, 0]));
  negative.forEach((review) => (review.topics || []).forEach((topic) => topicCounts.set(topic, (topicCounts.get(topic) || 0) + 1)));
  const topTopic = [...topicCounts.entries()].sort((left, right) => right[1] - left[1]).find((entry) => entry[1] > 0);
  document.querySelector("#top-topic").innerHTML = `<strong>${topTopic ? escapeHTML(TOPIC_LABELS[topTopic[0]]) : "—"}</strong>`;
  document.querySelector("#top-topic-detail").textContent = topTopic
    ? `${topTopic[1]} of ${negative.length} negative reviews`
    : "No topics mentioned in negative reviews";
}

function updateTopics(reviews) {
  const negative = reviews.filter((review) => review.sentiment === "negative");
  const counts = new Map(Object.keys(TOPIC_LABELS).map((topic) => [topic, 0]));
  negative.forEach((review) => (review.topics || []).forEach((topic) => counts.set(topic, (counts.get(topic) || 0) + 1)));
  const list = document.querySelector("#topic-list");
  list.replaceChildren();
  for (const [topic, label] of Object.entries(TOPIC_LABELS)) {
    const count = counts.get(topic);
    const share = negative.length ? Math.round((count / negative.length) * 100) : 0;
    const row = document.createElement("div");
    row.className = "topic-row";
    row.innerHTML = `
      <div class="topic-row-head"><span>${escapeHTML(label)}</span><span>${count} <span class="topic-share">· ${share}%</span></span></div>
      <div class="meter" role="progressbar" aria-label="${escapeHTML(label)} mentions"
        aria-valuemin="0" aria-valuemax="${Math.max(negative.length, 1)}" aria-valuenow="${count}">
        <span style="width:${share}%"></span>
      </div>`;
    list.append(row);
  }
  document.querySelector(".topic-panel .panel-help").textContent = negative.length
    ? `${negative.length} negative reviews in this selection. A review can mention more than one topic.`
    : "No negative reviews in this selection.";
}

function updateTrend(reviews) {
  const { from, to } = currentFilters();
  const weeks = new Map();
  if (from && to && from <= to) {
    const days = Math.round((new Date(`${to}T12:00:00Z`) - new Date(`${from}T12:00:00Z`)) / 86400000);
    const first = firstDayOfWeek(from);
    for (let offset = 0; offset <= days; offset += 7) {
      const week = shiftDate(first, offset);
      if (week <= to) weeks.set(week, { positive: 0, negative: 0 });
    }
  }
  for (const review of reviews) {
    const week = firstDayOfWeek(review.review_date);
    const entry = weeks.get(week);
    if (entry && (review.sentiment === "positive" || review.sentiment === "negative")) {
      entry[review.sentiment] += 1;
    }
  }
  const rows = [...weeks.entries()];
  const max = Math.max(1, ...rows.flatMap(([, counts]) => [counts.positive, counts.negative]));
  const chart = document.querySelector("#sentiment-chart");
  chart.replaceChildren();
  chart.setAttribute("aria-label", rows.map(([week, counts]) =>
    `Week of ${formatShortDate(week)}: ${counts.positive} positive, ${counts.negative} negative`
  ).join(". ") || "No sentiment data in this date range.");
  rows.forEach(([week, counts]) => {
    const row = document.createElement("div");
    row.className = "trend-row";
    row.innerHTML = `
      <span class="trend-date">${escapeHTML(formatShortDate(week))}</span>
      <div class="trend-bars">
        <div class="bar-line"><span class="bar-label">Positive</span><span class="bar-track"><i class="bar-positive" style="width:${(counts.positive / max) * 100}%"></i></span><b>${counts.positive}</b></div>
        <div class="bar-line"><span class="bar-label">Negative</span><span class="bar-track"><i class="bar-negative" style="width:${(counts.negative / max) * 100}%"></i></span><b>${counts.negative}</b></div>
      </div>`;
    chart.append(row);
  });
  document.querySelector("#trend-empty").hidden = reviews.length > 0;
}

function updateProperties(reviews, selectedProperty) {
  const keys = selectedProperty === "all" ? [...state.propertyNames.keys()] : [selectedProperty];
  const list = document.querySelector("#property-list");
  list.replaceChildren();
  keys.forEach((key) => {
    const matching = reviews.filter((review) => review.property_key === key);
    const score = average(matching);
    const card = document.createElement("article");
    card.className = "property-card";
    card.innerHTML = `
      <div class="property-card-top"><span class="property-name">${escapeHTML(state.propertyNames.get(key) || key)}</span>
        <span class="property-score">${score === null ? "—" : score.toFixed(1)}<small> / 10</small></span></div>
      <div class="property-meter" role="progressbar" aria-label="${escapeHTML(state.propertyNames.get(key) || key)} average rating"
        aria-valuemin="0" aria-valuemax="10" aria-valuenow="${score === null ? 0 : score}">
        <span style="width:${score === null ? 0 : Math.max(0, Math.min(score * 10, 100))}%"></span>
      </div>
      <div class="property-foot"><span>${matching.length} ${matching.length === 1 ? "review" : "reviews"}</span><span>${score === null ? "No rating data" : "Selected period"}</span></div>`;
    list.append(card);
  });
}

function updateFeed(reviews) {
  const feed = document.querySelector("#review-list");
  feed.replaceChildren();
  const ordered = [...reviews].sort((a, b) => b.review_date.localeCompare(a.review_date));
  document.querySelector("#feed-count").textContent = `${ordered.length} ${ordered.length === 1 ? "review" : "reviews"}`;
  document.querySelector("#review-empty").hidden = ordered.length > 0;
  ordered.slice(0, 30).forEach((review) => {
    const card = document.createElement("article");
    card.className = "review-item";
    const topicTags = (review.topics || []).map((topic) =>
      `<span class="topic-tag">${escapeHTML(TOPIC_LABELS[topic] || topic)}</span>`
    ).join("");
    const reviewParts = [];
    if (review.positive_text) reviewParts.push(`<p><span class="review-part-label">Positive</span>${escapeHTML(review.positive_text)}</p>`);
    if (review.negative_text) reviewParts.push(`<p><span class="review-part-label">Could improve</span>${escapeHTML(review.negative_text)}</p>`);
    if (!reviewParts.length && review.headline) reviewParts.push(`<p>${escapeHTML(review.headline)}</p>`);
    card.innerHTML = `
      <div class="review-meta">
        <div><strong>${escapeHTML(review.property_name || "Property")}</strong><span class="review-date">${escapeHTML(formatDate(review.review_date))}</span></div>
        <div class="review-meta-right"><span class="sentiment-pill sentiment-${escapeHTML(review.sentiment)}">${escapeHTML(review.sentiment)}</span>
          <span class="score-pill">${ratingValue(review.rating) === null ? "—" : review.rating.toFixed(1)}<small> / 10</small></span></div>
      </div>
      <div class="review-copy">${reviewParts.join("") || "<p>No written comment was provided.</p>"}</div>
      <div class="review-tags">${topicTags || "<span class=\"topic-tag topic-tag-muted\">No topic match</span>"}</div>`;
    feed.append(card);
  });
  if (ordered.length > 30) {
    const note = document.createElement("p");
    note.className = "feed-limit-note";
    note.textContent = `Showing 30 of ${ordered.length} reviews. Narrow the date range to find a specific review.`;
    feed.append(note);
  }
}

function updateFreshness(payload) {
  const notice = document.querySelector("#data-notice");
  const freshness = document.querySelector("#freshness-text");
  if (payload.dataset_type === "synthetic_demo_not_collected") {
    notice.hidden = false;
    notice.className = "data-notice demo-notice";
    notice.innerHTML = `<strong>Demo data</strong><span>${escapeHTML(payload.notice || "These records are fictional, not guest reviews.")}</span>`;
    freshness.textContent = "Sample records · not connected to Booking.com";
    return;
  }
  notice.hidden = true;
  const latestByProperty = new Map();
  for (const run of payload.collection_runs || []) {
    if (!latestByProperty.has(run.property_key)) latestByProperty.set(run.property_key, run);
  }
  const failedRuns = [...latestByProperty.values()].filter((run) => run.outcome === "failed").length;
  if (failedRuns) {
    notice.hidden = false;
    notice.className = "data-notice error-notice";
    notice.textContent = `${failedRuns} recent property sync${failedRuns === 1 ? "" : "s"} failed. Existing reviews are still shown.`;
  }
  freshness.textContent = payload.last_checked_at
    ? `Last checked ${formatTimestamp(payload.last_checked_at)}`
    : "No reviews collected yet";
}

function formatTimestamp(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium", timeStyle: "short", timeZone: "Australia/Sydney",
  }).format(date);
}

function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function render() {
  const filters = currentFilters();
  const error = document.querySelector("#filter-error");
  const invalidRange = !filters.from || !filters.to || filters.from > filters.to;
  error.hidden = !invalidRange;
  error.textContent = invalidRange ? "Choose a valid date range. The start date must be before the end date." : "";
  const reviews = selectedReviews(filters);
  updateSummary(reviews, filters);
  updateTopics(reviews);
  updateTrend(reviews);
  updateProperties(reviews, filters.property);
  updateFeed(reviews);
}

function setUpFilters(reviews) {
  const select = document.querySelector("#property-filter");
  const names = new Map((state.payload.properties || []).map((property) => [property.key, property.name]));
  reviews.forEach((review) => names.set(review.property_key, review.property_name || review.property_key));
  state.propertyNames = names;
  [...names.entries()].sort((a, b) => a[1].localeCompare(b[1])).forEach(([key, name]) => {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = name;
    select.append(option);
  });
  defaultWeek();
  [select, document.querySelector("#date-from"), document.querySelector("#date-to")]
    .forEach((control) => control.addEventListener("change", render));
  document.querySelector("#this-week").addEventListener("click", () => {
    defaultWeek();
    render();
  });
  document.querySelector("#clear-filters").addEventListener("click", () => {
    select.value = "all";
    defaultWeek();
    render();
  });
}

async function start() {
  const error = document.querySelector("#filter-error");
  try {
    const response = await fetch("/api/dashboard", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("The review data could not be loaded.");
    state.payload = await response.json();
    if (state.payload.error) throw new Error(state.payload.error);
    state.reviews = state.payload.reviews || [];
    updateFreshness(state.payload);
    setUpFilters(state.reviews);
    render();
  } catch (failure) {
    error.hidden = false;
    error.textContent = failure instanceof Error ? failure.message : "The review data could not be loaded.";
    document.querySelector("#freshness-text").textContent = "Data unavailable";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const filterPanel = document.querySelector(".filter-panel");
  const message = document.createElement("p");
  message.id = "filter-error";
  message.className = "filter-error";
  message.setAttribute("role", "alert");
  message.hidden = true;
  filterPanel.insertAdjacentElement("afterend", message);
  start();
});
