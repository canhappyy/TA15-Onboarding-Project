import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest


psycopg = pytest.importorskip("psycopg")

from src.functions.database_migration.handler import (  # noqa: E402
    DatabaseConnectionSettings,
    PsycopgMigrationRunner,
    load_migrations,
)
from src.repositories.api import BoundingBox, PostgresApiRepository  # noqa: E402


DATABASE_URL = os.getenv("TEST_DATABASE_URL")
MIGRATIONS_PATH = (
    Path(__file__).resolve().parents[4] / "packages" / "database" / "migrations"
)
REFERENCE_TIME = datetime(2026, 1, 15, 2, 0, tzinfo=timezone.utc)


def _prepare_database():
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


def _insert_sensor_fixtures():
    sensors = [
        (1, "Sensor One", "A", -37.810, 144.960),
        (2, "Sensor Two", "A", -37.815, 144.965),
        (3, "Inactive", "I", -37.812, 144.962),
        (4, "No Coordinates", "A", None, None),
        (5, "Live Only", "A", -37.820, 144.970),
        (6, "Outside", "A", -38.000, 145.300),
    ]
    minute_rows = [
        (1, "2026-01-15T12:10:00+11:00", 10, False),
        (1, "2026-01-15T12:55:00+11:00", 20, False),
        (1, "2026-01-15T12:00:00+11:00", 99, False),
        (1, "2026-01-15T12:50:00+11:00", 999, True),
        (1, "2026-01-15T13:01:00+11:00", 999, False),
        (2, "2026-01-14T11:00:00+11:00", 8, False),
        (3, "2026-01-15T12:45:00+11:00", 500, False),
        (3, "2026-01-15T13:10:00+11:00", 500, False),
        (4, "2026-01-15T13:20:00+11:00", 500, False),
        (5, "2026-01-15T12:40:00+11:00", 7, False),
    ]
    hourly_rows = [
        (1, "2026-01-11T12:00:00+11:00", 10, False),
        (1, "2026-01-12T12:00:00+11:00", 20, False),
        (1, "2026-01-13T12:00:00+11:00", 30, False),
        (1, "2026-01-14T12:00:00+11:00", 40, False),
        (1, "2026-01-14T13:00:00+11:00", 1000, True),
        (1, "2025-09-01T12:00:00+10:00", 999, False),
        (2, "2026-01-13T12:00:00+11:00", 10, False),
        (2, "2026-01-14T12:00:00+11:00", 20, False),
    ]
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO sensor_location (
                    location_id, sensor_name, status, latitude, longitude
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                sensors,
            )
            cursor.executemany(
                """
                INSERT INTO pedestrian_minute_count (
                    location_id, sensing_datetime, total_count, is_imputed
                ) VALUES (%s, %s, %s, %s)
                """,
                minute_rows,
            )
            cursor.executemany(
                """
                INSERT INTO pedestrian_hourly_count (
                    location_id, sensing_datetime, total_count, is_imputed
                ) VALUES (%s, %s, %s, %s)
                """,
                hourly_rows,
            )


def _insert_refuge_fixtures():
    records = [
        ("Community", "Library", "City Library", -37.810, 144.960, True),
        ("Assembly", "Museum", "Melbourne Museum", -37.815, 144.965, True),
        ("Leisure", "Public Garden", "City Garden", -37.820, 144.970, True),
        ("Leisure", "Public Park", "Flagstaff Park", -37.818, 144.958, True),
        ("Hospitality", "Cafe", "Busy Cafe", -37.812, 144.962, True),
        ("Community", "Library", "Outside Library", -38.000, 145.300, True),
        ("Community", "School", "Not Refuge", -37.811, 144.961, False),
    ]
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            for theme, sub_theme, name, latitude, longitude, is_refuge in records:
                cursor.execute(
                    """
                    INSERT INTO theme (theme, sub_theme)
                    VALUES (%s, %s)
                    ON CONFLICT (theme, sub_theme) DO UPDATE
                        SET sub_theme = EXCLUDED.sub_theme
                    RETURNING theme_id
                    """,
                    (theme, sub_theme),
                )
                theme_id = cursor.fetchone()[0]
                cursor.execute(
                    """
                    INSERT INTO landmark_category (
                        theme_id, category_name, is_refuge
                    ) VALUES (%s, %s, %s)
                    ON CONFLICT (theme_id, category_name) DO UPDATE
                        SET is_refuge = EXCLUDED.is_refuge
                    RETURNING category_id
                    """,
                    (theme_id, sub_theme, is_refuge),
                )
                category_id = cursor.fetchone()[0]
                cursor.execute(
                    """
                    INSERT INTO landmark (
                        category_id, feature_name, latitude, longitude
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    (category_id, name, latitude, longitude),
                )


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
def test_sensor_queries_return_observed_live_totals_and_historical_baselines():
    _prepare_database()
    _insert_sensor_fixtures()
    bounds = BoundingBox(-37.83, 144.94, -37.80, 144.99)

    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        repository = PostgresApiRepository(connection)
        conditions = repository.list_sensor_conditions(REFERENCE_TIME, bounds)
        latest = repository.get_latest_minute_timestamp()

    assert [condition.location_id for condition in conditions] == [1, 2, 5]
    first, second, live_only = conditions
    assert first.live_60_minute_total == 30
    assert first.latest_observed_at == datetime(
        2026, 1, 15, 1, 55, tzinfo=timezone.utc
    )
    assert first.historical_hourly_mean == 25.0
    assert first.historical_hourly_p75 == 32.5
    assert second.live_60_minute_total is None
    assert second.historical_hourly_mean == 15.0
    assert second.historical_hourly_p75 == 17.5
    assert live_only.live_60_minute_total == 7
    assert live_only.historical_hourly_mean is None
    assert live_only.historical_hourly_p75 is None
    assert latest == datetime(2026, 1, 15, 2, 1, tzinfo=timezone.utc)


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
def test_refuge_queries_map_categories_filter_bounds_and_run_read_only():
    _prepare_database()
    _insert_refuge_fixtures()
    bounds = BoundingBox(-37.83, 144.94, -37.80, 144.99)

    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        repository = PostgresApiRepository(connection)
        all_refuges = repository.list_refuges(bounds=bounds)
        filtered = repository.list_refuges(
            bounds=bounds,
            categories=["LIBRARY", "PARK"],
        )

    assert [(refuge.category, refuge.name) for refuge in all_refuges] == [
        ("GARDEN", "City Garden"),
        ("LIBRARY", "City Library"),
        ("MUSEUM", "Melbourne Museum"),
        ("PARK", "Flagstaff Park"),
    ]
    assert [(refuge.category, refuge.name) for refuge in filtered] == [
        ("LIBRARY", "City Library"),
        ("PARK", "Flagstaff Park"),
    ]
