"""Lightweight City of Melbourne Open Data sync client."""

from __future__ import annotations

import json
import socket
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets"
SENSOR_LOCATIONS_DATASET = "pedestrian-counting-system-sensor-locations"
MINUTE_COUNTS_DATASET = "pedestrian-counting-system-past-hour-counts-per-minute"
HOURLY_COUNTS_DATASET = "pedestrian-counting-system-monthly-counts-per-hour"
LANDMARKS_DATASET = (
    "landmarks-and-places-of-interest-including-schools-theatres-health-services-spor"
)

PAGE_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 15
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2
RETRYABLE_HTTP_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class OpenDataSyncError(RuntimeError):
    """Raised when an Open Data operation cannot complete."""


class OpenDataSyncTimeout(OpenDataSyncError):
    """Raised when every attempt times out."""


class OpenDataSyncResponseError(OpenDataSyncError):
    """Raised when Open Data returns an unusable response."""


def _request_json(url: str, params: dict[str, Any], timeout: int) -> Any:
    request = Request(
        f"{url}?{urlencode(params)}",
        headers={"Accept": "application/json"},
    )
    with urlopen(request, timeout=timeout) as response:
        try:
            return json.loads(response.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OpenDataSyncResponseError(
                "City of Melbourne Open Data returned malformed JSON"
            ) from error


class OpenDataSyncClient:
    def __init__(
        self,
        *,
        request_json: Callable[[str, dict[str, Any], int], Any] = _request_json,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._request_json = request_json
        self._sleep = sleep

    @staticmethod
    def records_url(dataset_id: str) -> str:
        return f"{BASE_URL}/{dataset_id}/records"

    def fetch_sensors(self) -> list[dict[str, Any]]:
        return self._fetch_records(SENSOR_LOCATIONS_DATASET)

    def fetch_landmarks(self) -> list[dict[str, Any]]:
        return self._fetch_records(LANDMARKS_DATASET)

    def fetch_minute_counts(
        self,
        watermark: datetime | None = None,
        overlap: timedelta = timedelta(minutes=30),
    ) -> list[dict[str, Any]]:
        if overlap < timedelta(0):
            raise ValueError("overlap must not be negative")
        if watermark is not None and watermark.utcoffset() is None:
            raise ValueError("watermark must be timezone-aware")

        anchor = watermark
        if anchor is None:
            latest = self._request_payload(
                self.records_url(MINUTE_COUNTS_DATASET),
                {"limit": 1, "order_by": "sensing_datetime DESC"},
            )["results"]
            if not latest:
                return []
            anchor = self._parse_source_timestamp(latest[0].get("sensing_datetime"))

        lower_bound = self._format_utc(anchor - overlap)
        return self._fetch_records(
            MINUTE_COUNTS_DATASET,
            where=f"sensing_datetime >= date'{lower_bound}'",
            order_by="sensing_datetime ASC",
        )

    def fetch_hourly_counts(
        self, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        if start_date >= end_date:
            raise ValueError("start_date must be before end_date")

        records: list[dict[str, Any]] = []
        current_date = start_date
        while current_date < end_date:
            next_date = current_date + timedelta(days=1)
            records.extend(
                self._fetch_records(
                    HOURLY_COUNTS_DATASET,
                    where=(
                        f"sensing_date >= date'{current_date.isoformat()}' "
                        f"AND sensing_date < date'{next_date.isoformat()}'"
                    ),
                    order_by="sensing_date ASC, hourday ASC, location_id ASC",
                )
            )
            current_date = next_date
        return records

    def _fetch_records(
        self,
        dataset_id: str,
        *,
        where: str | None = None,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset = 0

        while True:
            params: dict[str, Any] = {"limit": PAGE_SIZE, "offset": offset}
            if where is not None:
                params["where"] = where
            if order_by is not None:
                params["order_by"] = order_by

            payload = self._request_payload(self.records_url(dataset_id), params)
            page = payload["results"]
            records.extend(page)

            if (
                not page
                or len(page) < PAGE_SIZE
                or len(records) >= payload["total_count"]
            ):
                return records
            offset += PAGE_SIZE

    def _request_payload(
        self, url: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        for attempt in range(MAX_ATTEMPTS):
            try:
                payload = self._request_json(url, params, REQUEST_TIMEOUT_SECONDS)
                return self._validate_payload(payload)
            except HTTPError as error:
                if error.code not in RETRYABLE_HTTP_STATUS_CODES:
                    raise OpenDataSyncError(
                        "City of Melbourne Open Data rejected the request"
                    ) from None
                if attempt == MAX_ATTEMPTS - 1:
                    raise OpenDataSyncError(
                        "City of Melbourne Open Data is temporarily unavailable"
                    ) from None
            except (TimeoutError, socket.timeout):
                if attempt == MAX_ATTEMPTS - 1:
                    raise OpenDataSyncTimeout(
                        "City of Melbourne Open Data request timed out"
                    ) from None
            except URLError as error:
                if isinstance(error.reason, (TimeoutError, socket.timeout)):
                    if attempt == MAX_ATTEMPTS - 1:
                        raise OpenDataSyncTimeout(
                            "City of Melbourne Open Data request timed out"
                        ) from None
                elif attempt == MAX_ATTEMPTS - 1:
                    raise OpenDataSyncError(
                        "City of Melbourne Open Data request failed"
                    ) from None
            except OpenDataSyncResponseError:
                raise

            self._sleep(RETRY_BACKOFF_SECONDS * (2**attempt))

        raise AssertionError("retry loop exhausted")

    @staticmethod
    def _validate_payload(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise OpenDataSyncResponseError(
                "City of Melbourne Open Data returned a malformed response"
            )
        total_count = payload.get("total_count")
        results = payload.get("results")
        if (
            type(total_count) is not int
            or total_count < 0
            or not isinstance(results, list)
            or any(not isinstance(record, dict) for record in results)
        ):
            raise OpenDataSyncResponseError(
                "City of Melbourne Open Data returned a malformed response"
            )
        return payload

    @staticmethod
    def _parse_source_timestamp(value: Any) -> datetime:
        if not isinstance(value, str):
            raise OpenDataSyncResponseError(
                "City of Melbourne Open Data returned a malformed timestamp"
            )
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise OpenDataSyncResponseError(
                "City of Melbourne Open Data returned a malformed timestamp"
            ) from error
        if parsed.utcoffset() is None:
            raise OpenDataSyncResponseError(
                "City of Melbourne Open Data returned a malformed timestamp"
            )
        return parsed

    @staticmethod
    def _format_utc(value: datetime) -> str:
        return (
            value.astimezone(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
