"""Transparent, rule-based review labels and dashboard calculations."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timedelta
from statistics import mean
from zoneinfo import ZoneInfo


TOPIC_PATTERNS = {
    "cleanliness": (
        r"\bclean(?:liness)?\b", r"\bdirty\b", r"\bfilthy\b", r"\bstain(?:ed|s)?\b",
        r"\bdust(?:y)?\b", r"\bmould\b", r"\bmold\b", r"\btoilet\b", r"\bbathroom\b",
    ),
    "check_in": (
        r"\bcheck[ -]?in\b", r"\bcheck[ -]?out\b", r"\bkey(?:card)?s?\b", r"\baccess code\b",
        r"\bwait(?:ed|ing)?\b", r"\barrival\b", r"\bqueue\b",
    ),
    "staff": (
        r"\bstaff\b", r"\breception(?:ist)?\b", r"\bmanager\b", r"\bservice\b",
        r"\bhelpful\b", r"\bfriendly\b", r"\brude\b",
    ),
    "noise": (
        r"\bnoise\b", r"\bnoisy\b", r"\bloud\b", r"\btraffic\b", r"\bthin walls?\b",
        r"\bneighbou?rs?\b", r"\bmusic\b", r"\bsoundproof(?:ing)?\b",
    ),
    "facilities": (
        r"\bfacilit(?:y|ies)\b", r"\bwifi\b", r"\binternet\b", r"\blift\b", r"\belevator\b",
        r"\bair condition(?:ing)?\b", r"\bheater\b", r"\bshower\b", r"\bbreakfast\b",
    ),
    "location": (
        r"\blocation\b", r"\bnearby\b", r"\bclose to\b", r"\bwalk(?:ing)? distance\b",
        r"\bstation\b", r"\btransport\b", r"\bcentral\b", r"\bneighbourhood\b", r"\bneighborhood\b",
    ),
    "room_condition": (
        r"\broom\b", r"\bbed\b", r"\bmattress\b", r"\bfurniture\b", r"\bdated\b", r"\bbroken\b",
        r"\bsmall\b", r"\bspacious\b", r"\brenovat(?:ed|ion)\b",
    ),
    "value_for_money": (
        r"\bvalue\b", r"\bprice\b", r"\bcost\b", r"\bexpensive\b", r"\bcheap\b",
        r"\bworth\b", r"\bfor the money\b",
    ),
}

COMPILED_TOPICS = {
    topic: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for topic, patterns in TOPIC_PATTERNS.items()
}


def classify_sentiment(review: dict) -> str:
    """Use separate positive/negative text first, then the source score as fallback."""
    positive = _text(review.get("positive_text"))
    negative = _text(review.get("negative_text"))
    if positive and negative:
        return "mixed"
    if negative:
        return "negative"
    if positive:
        return "positive"

    score = review.get("rating")
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        if score >= 8:
            return "positive"
        if score <= 5:
            return "negative"
    return "mixed"


def classify_topics(review: dict) -> list[str]:
    text = " ".join(
        part for part in (
            _text(review.get("headline")),
            _text(review.get("positive_text")),
            _text(review.get("negative_text")),
        ) if part
    )
    return [
        topic for topic, patterns in COMPILED_TOPICS.items()
        if any(pattern.search(text) for pattern in patterns)
    ]


def annotate_review(review: dict) -> dict:
    """Return a copy with labels; the stored source record stays unchanged."""
    positive = _text(review.get("positive_text"))
    negative = _text(review.get("negative_text"))
    score = review.get("rating")
    conflict = (
        bool(positive and not negative and isinstance(score, (int, float)) and not isinstance(score, bool) and score <= 5)
        or bool(negative and not positive and isinstance(score, (int, float)) and not isinstance(score, bool) and score >= 8)
    )
    return {
        **review,
        "sentiment": classify_sentiment(review),
        "sentiment_conflict": conflict,
        "topics": classify_topics(review),
    }


def topic_summary(reviews: list[dict], *, sentiment: str = "negative") -> list[dict]:
    """Count each topic once per review; percentages use matching-sentiment reviews as denominator."""
    selected = [annotate_review(review) for review in reviews if classify_sentiment(review) == sentiment]
    denominator = len(selected)
    counts = Counter(topic for review in selected for topic in review["topics"])
    return [
        {
            "topic": topic,
            "count": counts[topic],
            "denominator": denominator,
            "percentage": round(100 * counts[topic] / denominator, 1) if denominator else 0.0,
        }
        for topic in TOPIC_PATTERNS
    ]


def weekly_rating_comparison(reviews: list[dict], *, now: datetime | None = None) -> dict:
    """Compare Sydney-local week-to-date against the same weekdays in the prior week."""
    timezone = ZoneInfo("Australia/Sydney")
    if now is None:
        local_now = datetime.now(timezone)
    elif now.tzinfo is None:
        local_now = now.replace(tzinfo=timezone)
    else:
        local_now = now.astimezone(timezone)
    today = local_now.date()
    week_start = today - timedelta(days=today.weekday())
    elapsed_days = (today - week_start).days
    previous_start = week_start - timedelta(days=7)
    previous_end = previous_start + timedelta(days=elapsed_days)

    current = _rating_period(reviews, week_start, today)
    previous = _rating_period(reviews, previous_start, previous_end)
    change = None
    if current["average"] is not None and previous["average"] is not None:
        change = round(current["average"] - previous["average"], 2)
    return {
        "timezone": "Australia/Sydney",
        "current_period": {"start": week_start.isoformat(), "end": today.isoformat(), **current},
        "previous_period": {"start": previous_start.isoformat(), "end": previous_end.isoformat(), **previous},
        "change": change,
    }


def property_rating_breakdown(reviews: list[dict]) -> list[dict]:
    grouped: dict[str, list[float]] = {}
    names: dict[str, str] = {}
    for review in reviews:
        key = str(review.get("property_key") or "unknown")
        names[key] = str(review.get("property_name") or key)
        score = review.get("rating")
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            grouped.setdefault(key, []).append(float(score))
        else:
            grouped.setdefault(key, [])
    return [
        {
            "property_key": key,
            "property_name": names[key],
            "review_count": len(scores),
            "average_rating": round(mean(scores), 2) if scores else None,
        }
        for key, scores in sorted(grouped.items())
    ]


def _rating_period(reviews: list[dict], start: date, end: date) -> dict:
    scores = []
    for review in reviews:
        review_date = _review_date(review.get("review_date"))
        score = review.get("rating")
        if start <= review_date <= end and isinstance(score, (int, float)) and not isinstance(score, bool):
            scores.append(float(score))
    return {
        "review_count": len(scores),
        "average": round(mean(scores), 2) if scores else None,
    }


def _review_date(value: object) -> date:
    if not isinstance(value, str):
        return date.min
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return date.min


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
