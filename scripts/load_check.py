"""Small concurrent HTTP smoke/load check for the local dashboard API."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen


def check_once(url: str) -> float:
    started = time.perf_counter()
    with urlopen(url, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"Dashboard returned HTTP {response.status}")
        payload = json.load(response)
    if payload.get("error") or not isinstance(payload.get("reviews"), list):
        raise RuntimeError("Dashboard API returned an invalid payload")
    return time.perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/dashboard")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()
    if args.requests < 1 or args.workers < 1:
        parser.error("--requests and --workers must be positive")

    started = time.perf_counter()
    durations = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(check_once, args.url) for _ in range(args.requests)]
        for future in as_completed(futures):
            durations.append(future.result())
    elapsed = time.perf_counter() - started
    ordered = sorted(durations)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print(
        f"{len(durations)} requests, {args.workers} workers; "
        f"{len(durations) / elapsed:.1f} requests/s; "
        f"mean {statistics.mean(durations) * 1000:.1f} ms; "
        f"p95 {p95 * 1000:.1f} ms; max {max(durations) * 1000:.1f} ms"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
