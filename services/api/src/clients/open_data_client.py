"""
Client for the City of Melbourne live Open Data API (OpenDataSoft v2.1).

Confirmed live response shape (verified against a real API call):
    {"total_count": 257575, "results": [{
        "location_id": 4,
        "sensing_datetime": "2026-08-03T14:17:00+00:00",   # UTC -- do not use directly
        "sensing_date": "2026-08-04",                       # Melbourne local date
        "sensing_time": "00:17",                             # Melbourne local time
        "direction_1": 1, "direction_2": 0, "total_of_directions": 1
    }]}

Two things this client handles because of that response:
  1. sensing_datetime from the API is UTC; sensing_date/sensing_time are
     already local. We rebuild a proper Melbourne-local timestamp from
     the date+time fields (using real DST rules, not a hardcoded
     +10:00) to match the convention the historical CSV pipeline uses.
  2. The "past hour" dataset actually holds ~257k records total, not an
     hour's worth -- so every fetch is filtered server-side to a recent
     time window instead of paginating the entire dataset.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets"
MINUTE_COUNTS_DATASET = "pedestrian-counting-system-past-hour-counts-per-minute"
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")

PAGE_SIZE = 100
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 15

# Confirmed against a live response -- no change needed if the API stays stable.
API_FIELDS = ["location_id", "sensing_date", "sensing_time", "direction_1", "direction_2", "total_of_directions"]


class OpenDataClientError(Exception):
    """Raised when the live API can't be reached or returns something unusable."""


def _get_with_retries(url: str, params: dict) -> dict:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("Open data API request failed (attempt %s/%s): %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise OpenDataClientError(f"Open data API unreachable after {MAX_RETRIES} attempts") from last_error


def _get_latest_available_timestamp(dataset_id: str) -> datetime | None:
    """Query the feed's own most recent record rather than assuming a fixed
    lag behind real time -- this dataset's actual publishing lag runs well
    beyond its documented 15-minute update cycle (confirmed: freshest
    record was ~20 min old even seconds after checking)."""
    url = f"{BASE_URL}/{dataset_id}/records"
    payload = _get_with_retries(url, {"limit": 1, "order_by": "sensing_datetime desc"})
    results = payload.get("results", [])
    if not results:
        return None
    return datetime.fromisoformat(results[0]["sensing_datetime"].replace("Z", "+00:00"))


def _recent_window_where(dataset_id: str, buffer_minutes: int = 5) -> tuple[str, datetime | None]:
    """Build an ODSQL filter anchored to the feed's own most recent
    timestamp, with a small buffer for records still trickling in."""
    latest = _get_latest_available_timestamp(dataset_id)
    if latest is None:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)  # fallback if feed is ever empty
    else:
        cutoff = latest - timedelta(minutes=buffer_minutes)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
    return f"sensing_datetime > date'{cutoff_str}'", latest


def fetch_records(dataset_id: str, where: str | None = None) -> list[dict]:
    """Fetch records for a dataset, paginating until exhausted. ALWAYS pass a `where`
    filter for recurring jobs against this dataset -- it holds ~250k+ rows total,
    not just 'the past hour' as the name suggests."""
    url = f"{BASE_URL}/{dataset_id}/records"
    records: list[dict] = []
    offset = 0

    while True:
        params = {"limit": PAGE_SIZE, "offset": offset}
        if where:
            params["where"] = where

        payload = _get_with_retries(url, params)
        page = payload.get("results", [])
        records.extend(page)

        total_count = payload.get("total_count", len(records))
        offset += PAGE_SIZE
        if offset >= total_count or not page:
            break

        if offset > 20_000:  # safety valve -- if this fires, the `where` filter isn't narrowing enough
            logger.error("fetch_records exceeded 20,000 rows for %s -- check the `where` filter", dataset_id)
            break

    logger.info("Fetched %s records from %s", len(records), dataset_id)
    return records


def _to_melbourne_datetime(sensing_date: str, sensing_time: str) -> str:
    """Build a correctly-offset local timestamp from the API's local date+time
    fields (NOT from the API's own sensing_datetime, which is UTC)."""
    naive = datetime.strptime(f"{sensing_date} {sensing_time}", "%Y-%m-%d %H:%M")
    localized = naive.replace(tzinfo=MELBOURNE_TZ)
    return localized.isoformat()


def fetch_minute_counts() -> pd.DataFrame:
    where, latest = _recent_window_where(MINUTE_COUNTS_DATASET)
    if latest:
        lag = datetime.now(timezone.utc) - latest
        logger.info("Live feed's freshest record is %s old (%s)", lag, latest.isoformat())

    raw_records = fetch_records(MINUTE_COUNTS_DATASET, where=where)

    if not raw_records:
        logger.warning("Open data API returned zero minute-count records (latest available: %s)", latest)
        return pd.DataFrame(columns=["Location_ID", "Sensing_DateTime", "Direction_1", "Direction_2", "Total_of_Directions"])
    
    df = pd.DataFrame(raw_records)
    missing = [f for f in API_FIELDS if f not in df.columns]
    if missing:
        raise OpenDataClientError(
            f"Live API response is missing expected fields {missing} -- "
            f"actual fields were {list(df.columns)}. The API schema may have changed."
        )

    df["Sensing_DateTime"] = df.apply(
        lambda r: _to_melbourne_datetime(r["sensing_date"], r["sensing_time"]), axis=1
    )

    return df.rename(
        columns={
            "location_id": "Location_ID",
            "direction_1": "Direction_1",
            "direction_2": "Direction_2",
            "total_of_directions": "Total_of_Directions",
        }
    )[["Location_ID", "Sensing_DateTime", "Direction_1", "Direction_2", "Total_of_Directions"]]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = fetch_minute_counts()
    print(result.head())
    print(f"{len(result)} rows fetched")