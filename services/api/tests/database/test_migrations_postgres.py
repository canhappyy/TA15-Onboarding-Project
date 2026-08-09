import os
from pathlib import Path
from urllib.parse import urlparse

import pytest


psycopg = pytest.importorskip("psycopg")

from src.functions.database_migration.handler import (  # noqa: E402
    DatabaseConnectionSettings,
    Migration,
    PsycopgMigrationRunner,
    PsycopgRouteReaderRoleDatabase,
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
            migrations[-1].version + 1,
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
            cursor.execute(
                "SELECT version FROM schema_migration WHERE version = %s",
                (migrations[-1].version + 1,),
            )
            assert cursor.fetchone() is None

    PsycopgRouteReaderRoleDatabase().ensure_reader(
        settings,
        "clearway_route_api",
        "reader-test-password",
    )
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            "CREATE ROLE route_reader_unexpected NOLOGIN"
        )
        connection.execute(
            "ALTER ROLE clearway_route_api CREATEDB CREATEROLE BYPASSRLS NOINHERIT"
        )
        connection.execute(
            "GRANT route_reader_unexpected TO clearway_route_api"
        )

    PsycopgRouteReaderRoleDatabase().ensure_reader(
        settings,
        "clearway_route_api",
        "reader-test-password",
    )
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rolcreatedb, rolcreaterole, rolbypassrls, rolinherit
                FROM pg_roles WHERE rolname = 'clearway_route_api'
                """
            )
            assert cursor.fetchone() == (False, False, False, True)
            cursor.execute(
                """
                SELECT parent.rolname
                FROM pg_auth_members AS membership
                JOIN pg_roles AS parent ON parent.oid = membership.roleid
                JOIN pg_roles AS member ON member.oid = membership.member
                WHERE member.rolname = 'clearway_route_api'
                ORDER BY parent.rolname
                """
            )
            assert cursor.fetchall() == [("clearway_api_readonly",)]
    reader_options = {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "dbname": parsed.path.removeprefix("/"),
        "user": "clearway_route_api",
        "password": "reader-test-password",
        "sslmode": "disable",
    }
    with psycopg.connect(**reader_options) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM sensor_location")
            assert cursor.fetchone() == (0,)

    for forbidden_statement in (
        "INSERT INTO sensor_location (location_id) VALUES (999999)",
        "UPDATE sensor_location SET sensor_name = 'forbidden'",
        "DELETE FROM sensor_location",
        "TRUNCATE sensor_location",
        "CREATE TABLE route_reader_forbidden (id INTEGER)",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(**reader_options) as connection:
                connection.execute(forbidden_statement)
