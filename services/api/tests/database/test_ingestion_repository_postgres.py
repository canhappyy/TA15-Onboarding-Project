import csv
import json
import os
from pathlib import Path

import pytest


psycopg = pytest.importorskip("psycopg")

from src.functions.database_migration.handler import (  # noqa: E402
    DatabaseConnectionSettings,
    PsycopgMigrationRunner,
    load_migrations,
)
from src.ingestion.pandas_adapter import (  # noqa: E402
    normalize_hourly_counts,
    normalize_landmarks,
    normalize_minute_counts,
    normalize_sensors,
)
from src.repositories.ingestion import IngestionCheckpoint, IngestionRepository  # noqa: E402


DATABASE_URL = os.getenv("TEST_DATABASE_URL")
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_PATH = REPOSITORY_ROOT / "packages" / "database" / "migrations"
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "pipeline"


def _fixture(name):
    with (FIXTURE_PATH / name).open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def _prepare_database():
    from urllib.parse import urlparse

    parsed = urlparse(DATABASE_URL)
    assert parsed.path.endswith("_test")
    settings = DatabaseConnectionSettings(
        host=parsed.hostname,
        port=parsed.port or 5432,
        dbname=parsed.path.removeprefix("/"),
        username=parsed.username,
        password=parsed.password,
        sslmode="disable",
    )
    PsycopgMigrationRunner().apply(settings, load_migrations(MIGRATIONS_PATH))
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE landmark, landmark_category, theme,
                    pedestrian_minute_count, pedestrian_hourly_count,
                    sensor_location, ingestion_checkpoint
                RESTART IDENTITY CASCADE
                """
            )


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
def test_repository_upserts_are_idempotent_and_checkpoint_is_readable():
    _prepare_database()
    sensors = normalize_sensors(_fixture("sensor_locations.csv"))["records"]
    minute = normalize_minute_counts(_fixture("minute_counts.csv"))["records"]
    hourly = normalize_hourly_counts(_fixture("hourly_counts.csv"))["records"]
    landmarks = normalize_landmarks(_fixture("landmarks.csv"))["records"]

    # Historical fixture references sensor 99; repository correctly requires sensors first.
    sensors.append({"location_id": 99, "sensor_name": "Historical 99", "status": "D"})

    with psycopg.connect(DATABASE_URL) as connection:
        repository = IngestionRepository(connection)
        first = {
            "sensors": repository.upsert_sensors(sensors),
            "minute": repository.upsert_minute_counts(minute),
            "hourly": repository.upsert_hourly_counts(hourly),
            "landmarks": repository.upsert_landmarks(landmarks),
        }
        second = {
            "sensors": repository.upsert_sensors(sensors),
            "minute": repository.upsert_minute_counts(minute),
            "hourly": repository.upsert_hourly_counts(hourly),
            "landmarks": repository.upsert_landmarks(landmarks),
        }
        repository.save_checkpoint(
            IngestionCheckpoint.succeeded(
                dataset="minute",
                watermark="2026-08-04T00:17:00+10:00",
                inserted_count=first["minute"].inserted,
                updated_count=first["minute"].updated,
                rejected_count=0,
                duplicates_resolved=1,
            )
        )

    assert all(stats.inserted > 0 for stats in first.values())
    assert all(stats.updated > 0 and stats.inserted == 0 for stats in second.values())

    with psycopg.connect(DATABASE_URL) as connection:
        repository = IngestionRepository(connection)
        checkpoint = repository.read_checkpoint("minute")
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM pedestrian_minute_count WHERE is_imputed = true")
            assert cursor.fetchone() == (0,)
            cursor.execute("SELECT COUNT(*) FROM landmark")
            assert cursor.fetchone() == (len(landmarks),)
    assert checkpoint.status == "succeeded"
    assert checkpoint.inserted_count == len(minute)


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
def test_caller_transaction_rolls_back_batch_and_checkpoint_together():
    _prepare_database()

    with pytest.raises(RuntimeError, match="force rollback"):
        with psycopg.connect(DATABASE_URL) as connection:
            repository = IngestionRepository(connection)
            repository.upsert_sensors([{"location_id": 500, "sensor_name": "Rollback"}])
            repository.save_checkpoint(IngestionCheckpoint.running("sensors"))
            raise RuntimeError("force rollback")

    with psycopg.connect(DATABASE_URL) as connection:
        repository = IngestionRepository(connection)
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM sensor_location WHERE location_id = 500")
            assert cursor.fetchone() == (0,)
        assert repository.read_checkpoint("sensors") is None
