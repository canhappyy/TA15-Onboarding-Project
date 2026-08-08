"""Application service connecting Open Data, normalizers, and PostgreSQL writes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from src.ingestion.pandas_adapter import (
    normalize_hourly_counts,
    normalize_landmarks,
    normalize_minute_counts,
    normalize_sensors,
)
from src.repositories.ingestion import (
    IngestionCheckpoint,
    IngestionRepository,
)


MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
MINUTE_OVERLAP = timedelta(minutes=30)
HOURLY_OVERLAP_DAYS = 1
BOOTSTRAP_DAYS = 90
SUPPORTED_MODES = frozenset(
    {"bootstrap", "minute", "hourly", "static", "status"}
)


class IngestionService:
    def __init__(
        self,
        *,
        client: Any,
        connection_factory: Callable[[], Any],
        repository_factory: Callable[[Any], Any] = IngestionRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._client = client
        self._connection_factory = connection_factory
        self._repository_factory = repository_factory
        self._clock = clock

    def run(self, mode: str) -> dict[str, Any]:
        if mode not in SUPPORTED_MODES:
            raise ValueError(f"Unsupported ingestion mode: {mode}")

        if mode == "status":
            return self._read_status()

        with self._connection_factory() as lock_connection:
            lock_repository = self._repository_factory(lock_connection)
            if not lock_repository.try_acquire_ingestion_lock():
                return {
                    "mode": mode,
                    "status": "skipped",
                    "reason": "INGESTION_ALREADY_RUNNING",
                    "datasets": {},
                }
            try:
                return self._run_locked(mode)
            finally:
                lock_repository.release_ingestion_lock()

    def _read_status(self) -> dict[str, Any]:
        with self._connection_factory() as connection:
            repository = self._repository_factory(connection)
            status = repository.read_ingestion_status()
        return {"mode": "status", **self._json_safe(status)}

    def _run_locked(self, mode: str) -> dict[str, Any]:
        datasets: dict[str, dict[str, int]] = {}
        if mode == "static":
            datasets["sensors"] = self._sync_sensors()
            datasets["landmarks"] = self._sync_landmarks()
        elif mode == "minute":
            datasets["minute"] = self._sync_minute()
        elif mode == "hourly":
            datasets["hourly"] = self._sync_scheduled_hourly()
        else:
            datasets["sensors"] = self._sync_sensors()
            datasets["hourly"] = self._sync_bootstrap_hourly()
            datasets["minute"] = self._sync_minute()
            datasets["landmarks"] = self._sync_landmarks()
        return {"mode": mode, "datasets": datasets}

    def _sync_sensors(self) -> dict[str, int]:
        started_at = self._clock()
        normalized = normalize_sensors(self._client.fetch_sensors())
        return self._write_batch(
            "sensors",
            normalized,
            lambda repository, records: repository.upsert_sensors(records),
            watermark=self._clock(),
            started_at=started_at,
        )

    def _sync_landmarks(self) -> dict[str, int]:
        started_at = self._clock()
        normalized = normalize_landmarks(self._client.fetch_landmarks())
        return self._write_batch(
            "landmarks",
            normalized,
            lambda repository, records: repository.upsert_landmarks(records),
            watermark=self._clock(),
            started_at=started_at,
        )

    def _sync_minute(self) -> dict[str, int]:
        checkpoint = self._read_checkpoint("minute")
        prior_watermark = checkpoint.watermark if checkpoint else None
        watermark = self._coerce_datetime(prior_watermark)
        started_at = self._clock()
        normalized = normalize_minute_counts(
            self._client.fetch_minute_counts(
                watermark=watermark,
                overlap=MINUTE_OVERLAP,
            )
        )
        next_watermark = self._latest_record_timestamp(
            normalized["records"],
            fallback=prior_watermark,
        )
        return self._write_batch(
            "minute",
            normalized,
            lambda repository, records: repository.upsert_minute_counts(records),
            watermark=next_watermark,
            started_at=started_at,
        )

    def _sync_scheduled_hourly(self) -> dict[str, int]:
        today = self._clock().astimezone(MELBOURNE_TZ).date()
        checkpoint = self._read_checkpoint("hourly")
        if checkpoint and checkpoint.watermark:
            completed_boundary = self._coerce_datetime(
                checkpoint.watermark
            ).astimezone(MELBOURNE_TZ).date()
            start_date = completed_boundary - timedelta(days=HOURLY_OVERLAP_DAYS)
        else:
            start_date = today - timedelta(days=1)
        return self._sync_hourly_range(start_date, today)

    def _sync_bootstrap_hourly(self) -> dict[str, int]:
        today = self._clock().astimezone(MELBOURNE_TZ).date()
        start_date = today - timedelta(days=BOOTSTRAP_DAYS)
        checkpoint = self._read_checkpoint("hourly")
        if checkpoint and checkpoint.watermark:
            completed_boundary = self._coerce_datetime(
                checkpoint.watermark
            ).astimezone(MELBOURNE_TZ).date()
            start_date = max(start_date, completed_boundary)
        return self._sync_hourly_range(start_date, today)

    def _sync_hourly_range(
        self, start_date: date, end_date: date
    ) -> dict[str, int]:
        aggregate = self._empty_summary(include_backfill=True)
        current_date = start_date
        while current_date < end_date:
            next_date = current_date + timedelta(days=1)
            started_at = self._clock()
            normalized = normalize_hourly_counts(
                self._client.fetch_hourly_counts(current_date, next_date)
            )
            boundary = datetime.combine(
                next_date,
                time.min,
                tzinfo=MELBOURNE_TZ,
            ).astimezone(timezone.utc)
            summary = self._write_hourly_batch(
                normalized,
                watermark=boundary,
                started_at=started_at,
            )
            for key, value in summary.items():
                aggregate[key] += value
            current_date = next_date
        return aggregate

    def _write_hourly_batch(
        self,
        normalized: dict[str, Any],
        *,
        watermark: datetime,
        started_at: datetime,
    ) -> dict[str, int]:
        records = normalized["records"]
        location_ids = {record["location_id"] for record in records}
        with self._connection_factory() as connection:
            repository = self._repository_factory(connection)
            existing_ids = repository.read_existing_sensor_ids(location_ids)
            missing_ids = sorted(location_ids - existing_ids)
            if missing_ids:
                repository.upsert_sensors(
                    [
                        {
                            "location_id": location_id,
                            "sensor_name": f"Unknown historical sensor {location_id}",
                            "status": "I",
                        }
                        for location_id in missing_ids
                    ]
                )
            stats = repository.upsert_hourly_counts(records)
            repository.save_checkpoint(
                self._succeeded_checkpoint(
                    "hourly",
                    normalized,
                    stats,
                    watermark=watermark,
                    started_at=started_at,
                )
            )
        summary = self._summary(normalized, stats)
        summary["backfilled_sensors"] = len(missing_ids)
        return summary

    def _write_batch(
        self,
        dataset: str,
        normalized: dict[str, Any],
        writer: Callable[[Any, list[dict[str, Any]]], Any],
        *,
        watermark: datetime | str | None,
        started_at: datetime,
    ) -> dict[str, int]:
        with self._connection_factory() as connection:
            repository = self._repository_factory(connection)
            stats = writer(repository, normalized["records"])
            repository.save_checkpoint(
                self._succeeded_checkpoint(
                    dataset,
                    normalized,
                    stats,
                    watermark=watermark,
                    started_at=started_at,
                )
            )
        return self._summary(normalized, stats)

    def _read_checkpoint(self, dataset: str) -> IngestionCheckpoint | None:
        with self._connection_factory() as connection:
            return self._repository_factory(connection).read_checkpoint(dataset)

    def _succeeded_checkpoint(
        self,
        dataset: str,
        normalized: dict[str, Any],
        stats: Any,
        *,
        watermark: datetime | str | None,
        started_at: datetime,
    ) -> IngestionCheckpoint:
        return IngestionCheckpoint.succeeded(
            dataset=dataset,
            watermark=watermark,
            inserted_count=stats.inserted,
            updated_count=stats.updated,
            rejected_count=normalized["rejected_count"],
            duplicates_resolved=normalized["duplicates_resolved"],
            started_at=started_at,
            completed_at=self._clock(),
        )

    @staticmethod
    def _summary(normalized: dict[str, Any], stats: Any) -> dict[str, int]:
        return {
            "inserted": stats.inserted,
            "updated": stats.updated,
            "rejected": normalized["rejected_count"],
            "duplicates_resolved": normalized["duplicates_resolved"],
        }

    @staticmethod
    def _empty_summary(*, include_backfill: bool = False) -> dict[str, int]:
        summary = {
            "inserted": 0,
            "updated": 0,
            "rejected": 0,
            "duplicates_resolved": 0,
        }
        if include_backfill:
            summary["backfilled_sensors"] = 0
        return summary

    @staticmethod
    def _coerce_datetime(value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        parsed = (
            value
            if isinstance(value, datetime)
            else datetime.fromisoformat(value.replace("Z", "+00:00"))
        )
        if parsed.utcoffset() is None:
            raise ValueError("Checkpoint watermark must be timezone-aware")
        return parsed

    @staticmethod
    def _latest_record_timestamp(
        records: list[dict[str, Any]],
        *,
        fallback: datetime | str | None,
    ) -> datetime | str | None:
        if not records:
            return fallback
        return max(
            (record["sensing_datetime"] for record in records),
            key=lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")),
        )

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: IngestionService._json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [IngestionService._json_safe(item) for item in value]
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return value
