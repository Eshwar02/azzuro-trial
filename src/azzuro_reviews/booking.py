"""Small client for Booking.com's authorized Guest Review API."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


TOKEN_URL = "https://connectivity-authentication.booking.com/token-based-authentication/exchange"
REVIEWS_ROOT = "https://supply-xml.booking.com/review-api/properties"
ALLOWED_API_HOST = "supply-xml.booking.com"
TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 4
RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


class BookingAPIError(RuntimeError):
    """A safe-to-log API error that does not include response bodies or secrets."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class BookingClient:
    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None

    def _request_json(self, url: str, *, method: str = "GET", body: dict | None = None,
                      authenticated: bool = False, refresh_on_unauthorized: bool = False) -> dict:
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        refreshed = False
        attempt = 0
        while attempt < MAX_ATTEMPTS:
            headers = {"Accept": "application/json"}
            if payload is not None:
                headers["Content-Type"] = "application/json"
            if authenticated:
                headers["Authorization"] = "Bearer " + self._access_token()
            request = Request(url, data=payload, headers=headers, method=method)
            try:
                with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                    result = json.loads(response.read().decode("utf-8"))
                if not isinstance(result, dict):
                    raise BookingAPIError("Booking.com returned an unexpected JSON response")
                return result
            except HTTPError as exc:
                if exc.code == 401 and authenticated and refresh_on_unauthorized and not refreshed:
                    self._token = None
                    refreshed = True
                    continue
                if exc.code not in RETRYABLE_STATUS_CODES or attempt == MAX_ATTEMPTS - 1:
                    raise BookingAPIError(f"Booking.com request failed with HTTP {exc.code}", exc.code) from None
                time.sleep(self._retry_delay(exc.headers.get("Retry-After"), attempt))
                attempt += 1
            except (URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
                if attempt == MAX_ATTEMPTS - 1:
                    reason = "network/timeout" if isinstance(exc, (URLError, TimeoutError)) else "invalid response"
                    raise BookingAPIError(f"Booking.com request failed ({reason})") from None
                time.sleep(2 ** attempt)
                attempt += 1
        raise BookingAPIError("Booking.com request failed after retries")

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        if retry_after:
            try:
                return min(max(float(retry_after), 0), 30)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(retry_after).timestamp() - time.time())
                    return min(max(delay, 0), 30)
                except (TypeError, ValueError, OverflowError):
                    pass
        return float(min(2 ** attempt, 8))

    def _access_token(self) -> str:
        if self._token is None:
            response = self._request_json(
                TOKEN_URL,
                method="POST",
                body={"client_id": self._client_id, "client_secret": self._client_secret},
            )
            token = response.get("jwt")
            if not isinstance(token, str) or not token:
                raise BookingAPIError("Token exchange did not return a JWT")
            self._token = token
        return self._token

    def reviews(self, hotel_id: str, from_date: str) -> Iterator[dict]:
        url = f"{REVIEWS_ROOT}/{hotel_id}/reviews?from_date={from_date}"
        visited: set[str] = set()
        while url:
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname != ALLOWED_API_HOST or parsed.port not in (None, 443):
                raise BookingAPIError("Booking.com returned an unexpected pagination URL")
            if url in visited:
                raise BookingAPIError("Booking.com repeated a pagination URL")
            visited.add(url)

            response = self._request_json(
                url, authenticated=True, refresh_on_unauthorized=True
            )
            errors = response.get("errors") or []
            if errors:
                raise BookingAPIError("Booking.com returned an API error for the review request")
            data = response.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("reviews"), list):
                raise BookingAPIError("Booking.com returned an invalid review response")
            page_reviews = data["reviews"]
            if not page_reviews:
                return
            for review in page_reviews:
                if isinstance(review, dict):
                    yield review
                else:
                    raise BookingAPIError("Booking.com returned an invalid review record")

            meta = response.get("meta") or {}
            if not isinstance(meta, dict):
                raise BookingAPIError("Booking.com returned invalid pagination metadata")
            next_page = meta.get("next_page")
            if not next_page:
                return
            if not isinstance(next_page, str):
                raise BookingAPIError("Booking.com returned an invalid pagination link")
            url = next_page
