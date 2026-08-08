"""Transactional PostgreSQL writes for normalized ingestion records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


INGESTION_LOCK_ID = 1_512_000_002


@dataclass(frozen=True)
class WriteStats:
    inserted: int
    updated: int


@dataclass(frozen=True)
class IngestionCheckpoint:
    dataset: str
    watermark: datetime | str | None
    last_started_at: datetime
    last_completed_at: datetime | None
    status: str
    inserted_count: int = 0
    updated_count: int = 0
    rejected_count: int = 0
    duplicates_resolved: int = 0
    error_message: str | None = None

    @classmethod
    def running(
        cls, dataset: str, *, started_at: datetime | None = None
    ) -> IngestionCheckpoint:
        return cls(
            dataset=dataset,
            watermark=None,
            last_started_at=started_at or datetime.now(timezone.utc),
            last_completed_at=None,
            status="running",
        )

    @classmethod
    def succeeded(
        cls,
        dataset: str,
        watermark: datetime | str | None,
        inserted_count: int,
        updated_count: int,
        rejected_count: int,
        duplicates_resolved: int,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> IngestionCheckpoint:
        completed = completed_at or datetime.now(timezone.utc)
        return cls(
            dataset=dataset,
            watermark=watermark,
            last_started_at=started_at or completed,
            last_completed_at=completed,
            status="succeeded",
            inserted_count=inserted_count,
            updated_count=updated_count,
            rejected_count=rejected_count,
            duplicates_resolved=duplicates_resolved,
        )


class IngestionRepository:
    """Write normalized batches using a caller-owned psycopg connection."""

    SENSOR_COLUMNS = (
        "location_id",
        "sensor_description",
        "sensor_name",
        "installation_date",
        "note",
        "location_type",
        "status",
        "direction_1_label",
        "direction_2_label",
        "latitude",
        "longitude",
    )
    COUNT_COLUMNS = (
        "location_id",
        "sensing_datetime",
        "direction_1_count",
        "direction_2_count",
        "total_count",
        "is_imputed",
    )

    def __init__(self, connection: Any):
        self._connection = connection

    def try_acquire_ingestion_lock(self) -> bool:
        """Acquire the process-wide session lock without waiting."""
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", (INGESTION_LOCK_ID,))
            acquired = bool(cursor.fetchone()[0])
        self._connection.commit()
        return acquired

    def release_ingestion_lock(self) -> bool:
        """Release the process-wide session lock held by this connection."""
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", (INGESTION_LOCK_ID,))
            released = bool(cursor.fetchone()[0])
        self._connection.commit()
        return released

    def upsert_sensors(self, records: Iterable[Mapping[str, Any]]) -> WriteStats:
        parameters = self._parameters(records, self.SENSOR_COLUMNS)
        if not parameters:
            return WriteStats(0, 0)

        statement = """
            INSERT INTO sensor_location (
                location_id, sensor_description, sensor_name, installation_date,
                note, location_type, status, direction_1_label,
                direction_2_label, latitude, longitude
            ) VALUES (
                %(location_id)s, %(sensor_description)s, %(sensor_name)s,
                %(installation_date)s, %(note)s, %(location_type)s, %(status)s,
                %(direction_1_label)s, %(direction_2_label)s, %(latitude)s,
                %(longitude)s
            )
            ON CONFLICT (location_id) DO UPDATE SET
                sensor_description = EXCLUDED.sensor_description,
                sensor_name = EXCLUDED.sensor_name,
                installation_date = EXCLUDED.installation_date,
                note = EXCLUDED.note,
                location_type = EXCLUDED.location_type,
                status = EXCLUDED.status,
                direction_1_label = EXCLUDED.direction_1_label,
                direction_2_label = EXCLUDED.direction_2_label,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude
            RETURNING (xmax = 0) AS inserted
        """
        return self._execute_batch(statement, parameters)

    def upsert_minute_counts(
        self, records: Iterable[Mapping[str, Any]]
    ) -> WriteStats:
        return self._upsert_counts(
            records,
            table="pedestrian_minute_count",
            conflict_key="sensing_datetime, location_id",
        )

    def upsert_hourly_counts(
        self, records: Iterable[Mapping[str, Any]]
    ) -> WriteStats:
        return self._upsert_counts(
            records,
            table="pedestrian_hourly_count",
            conflict_key="location_id, sensing_datetime",
        )

    def upsert_landmarks(
        self, records: Iterable[Mapping[str, Any]]
    ) -> WriteStats:
        records = list(records)
        if not records:
            return WriteStats(0, 0)

        landmark_parameters = []
        with self._connection.cursor() as cursor:
            for record in records:
                cursor.execute(
                    """
                    INSERT INTO theme (theme, sub_theme)
                    VALUES (%s, %s)
                    ON CONFLICT (theme, sub_theme) DO UPDATE
                        SET sub_theme = EXCLUDED.sub_theme
                    RETURNING theme_id
                    """,
                    (record.get("theme"), record.get("sub_theme")),
                )
                theme_id = cursor.fetchone()[0]
                cursor.execute(
                    """
                    INSERT INTO landmark_category (
                        theme_id, category_name, is_refuge
                    ) VALUES (%s, %s, %s)
                    ON CONFLICT (theme_id, category_name) DO UPDATE
                        SET category_name = EXCLUDED.category_name,
                            is_refuge = EXCLUDED.is_refuge
                    RETURNING category_id
                    """,
                    (
                        theme_id,
                        record.get("sub_theme"),
                        record.get("refuge_category") is not None,
                    ),
                )
                category_id = cursor.fetchone()[0]
                landmark_parameters.append(
                    {
                        "category_id": category_id,
                        "feature_name": record.get("feature_name"),
                        "latitude": record.get("latitude"),
                        "longitude": record.get("longitude"),
                    }
                )

            cursor.executemany(
                """
                INSERT INTO landmark (
                    category_id, feature_name, latitude, longitude
                ) VALUES (
                    %(category_id)s, %(feature_name)s, %(latitude)s,
                    %(longitude)s
                )
                ON CONFLICT (category_id, feature_name, latitude, longitude)
                DO UPDATE SET feature_name = EXCLUDED.feature_name
                RETURNING (xmax = 0) AS inserted
                """,
                landmark_parameters,
                returning=True,
            )
            return self._result_stats(cursor)

    def save_checkpoint(self, checkpoint: IngestionCheckpoint) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ingestion_checkpoint (
                    dataset, watermark, last_started_at, last_completed_at,
                    status, inserted_count, updated_count, rejected_count,
                    duplicates_resolved, error_message
                ) VALUES (
                    %(dataset)s, %(watermark)s, %(last_started_at)s,
                    %(last_completed_at)s, %(status)s, %(inserted_count)s,
                    %(updated_count)s, %(rejected_count)s,
                    %(duplicates_resolved)s, %(error_message)s
                )
                ON CONFLICT (dataset) DO UPDATE SET
                    watermark = EXCLUDED.watermark,
                    last_started_at = EXCLUDED.last_started_at,
                    last_completed_at = EXCLUDED.last_completed_at,
                    status = EXCLUDED.status,
                    inserted_count = EXCLUDED.inserted_count,
                    updated_count = EXCLUDED.updated_count,
                    rejected_count = EXCLUDED.rejected_count,
                    duplicates_resolved = EXCLUDED.duplicates_resolved,
                    error_message = EXCLUDED.error_message
                """,
                asdict(checkpoint),
            )

    def read_checkpoint(self, dataset: str) -> IngestionCheckpoint | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT dataset, watermark, last_started_at, last_completed_at,
                    status, inserted_count, updated_count, rejected_count,
                    duplicates_resolved, error_message
                FROM ingestion_checkpoint
                WHERE dataset = %s
                """,
                (dataset,),
            )
            row = cursor.fetchone()
        return IngestionCheckpoint(*row) if row else None

    def read_existing_sensor_ids(self, location_ids: Iterable[int]) -> set[int]:
        location_ids = sorted(set(location_ids))
        if not location_ids:
            return set()
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT location_id
                FROM sensor_location
                WHERE location_id = ANY(%s)
                """,
                (location_ids,),
            )
            return {row[0] for row in cursor.fetchall()}

    def _upsert_counts(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        table: str,
        conflict_key: str,
    ) -> WriteStats:
        parameters = self._parameters(
            records, self.COUNT_COLUMNS, defaults={"is_imputed": False}
        )
        if not parameters:
            return WriteStats(0, 0)
        statement = f"""
            INSERT INTO {table} (
                location_id, sensing_datetime, direction_1_count,
                direction_2_count, total_count, is_imputed
            ) VALUES (
                %(location_id)s, %(sensing_datetime)s, %(direction_1_count)s,
                %(direction_2_count)s, %(total_count)s, %(is_imputed)s
            )
            ON CONFLICT ({conflict_key}) DO UPDATE SET
                direction_1_count = EXCLUDED.direction_1_count,
                direction_2_count = EXCLUDED.direction_2_count,
                total_count = EXCLUDED.total_count,
                is_imputed = EXCLUDED.is_imputed
            RETURNING (xmax = 0) AS inserted
        """
        return self._execute_batch(statement, parameters)

    def _execute_batch(
        self, statement: str, parameters: list[dict[str, Any]]
    ) -> WriteStats:
        with self._connection.cursor() as cursor:
            cursor.executemany(statement, parameters, returning=True)
            return self._result_stats(cursor)

    @staticmethod
    def _result_stats(cursor: Any) -> WriteStats:
        outcomes = []
        while True:
            row = cursor.fetchone()
            if row is not None:
                outcomes.append(bool(row[0]))
            if not cursor.nextset():
                break
        inserted = sum(outcomes)
        return WriteStats(inserted=inserted, updated=len(outcomes) - inserted)

    @staticmethod
    def _parameters(
        records: Iterable[Mapping[str, Any]],
        columns: tuple[str, ...],
        *,
        defaults: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        defaults = defaults or {}
        return [
            {column: record.get(column, defaults.get(column)) for column in columns}
            for record in records
        ]
