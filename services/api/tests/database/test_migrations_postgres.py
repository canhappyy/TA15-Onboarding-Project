import os
from pathlib import Path
from urllib.parse import urlparse

import pytest


psycopg = pytest.importorskip("psycopg")

from src.functions.database_migration.handler import (  # noqa: E402
    DatabaseConnectionSettings,
    Migration,
    PsycopgMigrationRunner,
    load_migrations,
)


DATABASE_URL = os.getenv("TEST_DATABASE_URL")
MIGRATIONS_PATH = Path(__file__).resolve().parents[4] / "packages" / "database" / "migrations"


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
def test_migrations_apply_to_empty_postgres_and_are_idempotent():
    parsed = urlparse(DATABASE_URL)
    assert parsed.path.endswith("_test"), "Integration test requires a dedicated *_test database"

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA public CASCADE")
            cursor.execute("CREATE SCHEMA public")

    settings = DatabaseConnectionSettings(
        host=parsed.hostname,
        port=parsed.port or 5432,
        dbname=parsed.path.removeprefix("/"),
        username=parsed.username,
        password=parsed.password,
        sslmode="disable",
    )
    migrations = load_migrations(MIGRATIONS_PATH)
    runner = PsycopgMigrationRunner()

    first = runner.apply(settings, migrations)
    second = runner.apply(settings, migrations)

    assert first == [migration.version for migration in migrations]
    assert second == []
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                """
            )
            tables = {row[0] for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public'
                """
            )
            indexes = {row[0] for row in cursor.fetchall()}
    assert {
        "schema_migration",
        "ingestion_checkpoint",
        "sensor_location",
        "pedestrian_minute_count",
        "pedestrian_hourly_count",
        "theme",
        "landmark_category",
        "landmark",
    } <= tables
    assert "landmark_natural_key" in indexes

    broken_migrations = [
        *migrations,
        Migration(
            3,
            "broken",
            "CREATE TABLE rollback_probe (id INTEGER); SELECT missing_column FROM rollback_probe;",
        ),
    ]
    with pytest.raises(psycopg.Error):
        runner.apply(settings, broken_migrations)

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.rollback_probe')")
            assert cursor.fetchone() == (None,)
            cursor.execute("SELECT version FROM schema_migration WHERE version = 3")
            assert cursor.fetchone() is None
