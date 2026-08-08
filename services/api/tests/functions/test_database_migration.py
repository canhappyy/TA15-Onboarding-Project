import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import src.functions.database_migration.handler as migration_handler
from src.functions.database_migration.handler import (
    DatabaseConnectionSettings,
    DatabaseCredentials,
    Migration,
    PsycopgMigrationRunner,
    SecretsManagerSecretReader,
    lambda_handler,
    load_migrations,
)


class FakeSecretReader:
    def __init__(self, credentials):
        self.credentials = credentials
        self.requested_arn = None

    def get_database_credentials(self, secret_arn):
        self.requested_arn = secret_arn
        return self.credentials


class FakeMigrationRunner:
    def __init__(self, applied=None, error=None):
        self.applied = applied or []
        self.error = error
        self.settings = None
        self.migrations = None

    def apply(self, settings, migrations):
        self.settings = settings
        self.migrations = migrations
        if self.error:
            raise self.error
        return self.applied


class FakeSecretsManagerClient:
    def __init__(self, payload):
        self.payload = payload

    def get_secret_value(self, SecretId):
        self.secret_id = SecretId
        return {"SecretString": json.dumps(self.payload)}


class FakeCursor:
    def __init__(self, applied_versions=()):
        self.applied_versions = applied_versions
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters=None):
        self.statements.append((str(statement), parameters))

    def fetchall(self):
        return [(version,) for version in self.applied_versions]


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.exit_error_type = None

    def __enter__(self):
        return self

    def __exit__(self, error_type, _error, _traceback):
        self.exit_error_type = error_type
        return False

    def cursor(self):
        return self.fake_cursor


def test_load_migrations_sorts_versioned_sql(tmp_path):
    (tmp_path / "0002_checkpoint.sql").write_text("SELECT 2;")
    (tmp_path / "0001_initial.sql").write_text("SELECT 1;")

    migrations = load_migrations(tmp_path)

    assert [migration.version for migration in migrations] == [1, 2]
    assert [migration.name for migration in migrations] == ["initial", "checkpoint"]


def test_load_migrations_rejects_duplicate_versions(tmp_path):
    (tmp_path / "0001_initial.sql").write_text("SELECT 1;")
    (tmp_path / "0001_duplicate.sql").write_text("SELECT 2;")

    with pytest.raises(ValueError, match="Duplicate migration version"):
        load_migrations(tmp_path)


def test_runner_uses_tls_lock_and_skips_applied_migrations():
    cursor = FakeCursor(applied_versions=(1,))
    connection = FakeConnection(cursor)
    captured = {}

    def connect(**options):
        captured.update(options)
        return connection

    settings = DatabaseConnectionSettings(
        host="private.example.internal",
        port=5432,
        dbname="clearway",
        username="clearway_admin",
        password="secret",
    )
    migrations = [
        Migration(1, "initial", "CREATE TABLE one (id INTEGER);"),
        Migration(2, "checkpoint", "CREATE TABLE two (id INTEGER);"),
    ]

    applied = PsycopgMigrationRunner(connect=connect).apply(settings, migrations)
    statements = "\n".join(statement for statement, _ in cursor.statements)

    assert captured["sslmode"] == "require"
    assert "pg_advisory_xact_lock" in statements
    assert "CREATE TABLE IF NOT EXISTS schema_migration" in statements
    assert "CREATE TABLE one" not in statements
    assert "CREATE TABLE two" in statements
    assert applied == [2]


def test_runner_leaves_transaction_rollback_to_connection_on_failure():
    class FailingCursor(FakeCursor):
        def execute(self, statement, parameters=None):
            super().execute(statement, parameters)
            if "BROKEN SQL" in str(statement):
                raise RuntimeError("migration failed")

    connection = FakeConnection(FailingCursor())
    runner = PsycopgMigrationRunner(connect=lambda **_options: connection)
    settings = DatabaseConnectionSettings("host", 5432, "clearway", "user", "secret")

    with pytest.raises(RuntimeError, match="migration failed"):
        runner.apply(settings, [Migration(1, "broken", "BROKEN SQL")])

    assert connection.exit_error_type is RuntimeError


def test_handler_reads_secret_and_applies_packaged_migrations(tmp_path):
    (tmp_path / "0001_initial.sql").write_text("SELECT 1;")
    credentials = DatabaseCredentials("clearway_admin", "secret")
    reader = FakeSecretReader(credentials)
    runner = FakeMigrationRunner(applied=[1])
    environment = {
        "DATABASE_HOST": "private.example.internal",
        "DATABASE_PORT": "5432",
        "DATABASE_NAME": "clearway",
        "DATABASE_SECRET_ARN": "secret-arn",
        "MIGRATIONS_PATH": str(tmp_path),
    }

    with patch.dict(os.environ, environment, clear=True):
        response = lambda_handler({}, None, secret_reader=reader, migration_runner=runner)

    assert response == {"status": "ok", "applied": 1, "current_version": 1}
    assert reader.requested_arn == "secret-arn"
    assert runner.settings.password == "secret"
    assert [migration.version for migration in runner.migrations] == [1]


def test_handler_sanitizes_failure_logs(tmp_path):
    (tmp_path / "0001_initial.sql").write_text("SELECT 1;")
    reader = FakeSecretReader(DatabaseCredentials("clearway_admin", "super-secret"))
    runner = FakeMigrationRunner(error=ValueError("super-secret private.example.internal"))
    environment = {
        "DATABASE_HOST": "private.example.internal",
        "DATABASE_PORT": "5432",
        "DATABASE_NAME": "clearway",
        "DATABASE_SECRET_ARN": "secret-arn",
        "MIGRATIONS_PATH": str(tmp_path),
    }

    with patch.dict(os.environ, environment, clear=True):
        with pytest.raises(RuntimeError, match="Database migration failed"):
            with patch.object(migration_handler.LOGGER, "error") as logger:
                lambda_handler({}, None, secret_reader=reader, migration_runner=runner)

    logged = str(logger.call_args)
    assert "super-secret" not in logged
    assert "private.example.internal" not in logged


def test_secret_reader_requires_username_and_password():
    reader = SecretsManagerSecretReader(client=FakeSecretsManagerClient({"username": "admin"}))

    with pytest.raises(ValueError, match="missing required credentials"):
        reader.get_database_credentials("secret-arn")
