import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path


LOGGER = logging.getLogger("database_migration")
LOGGER.setLevel(logging.INFO)
MIGRATION_FILENAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
MIGRATION_LOCK_ID = 1_512_000_001


@dataclass(frozen=True)
class DatabaseConnectionSettings:
    host: str
    port: int
    dbname: str
    username: str
    password: str
    sslmode: str = "require"


@dataclass(frozen=True)
class DatabaseCredentials:
    username: str
    password: str


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str


class SecretsManagerSecretReader:
    def __init__(self, client=None):
        if client is None:
            import boto3

            client = boto3.client("secretsmanager")
        self._client = client

    def get_database_credentials(self, secret_arn):
        response = self._client.get_secret_value(SecretId=secret_arn)
        payload = json.loads(response["SecretString"])
        if any(key not in payload for key in ("username", "password")):
            raise ValueError("RDS-managed secret is missing required credentials")
        return DatabaseCredentials(payload["username"], payload["password"])


class PsycopgMigrationRunner:
    def __init__(self, connect=None):
        if connect is None:
            from psycopg import connect

        self._connect = connect

    def apply(self, settings, migrations):
        with self._connect(
            host=settings.host,
            port=settings.port,
            dbname=settings.dbname,
            user=settings.username,
            password=settings.password,
            sslmode=settings.sslmode,
            connect_timeout=5,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migration (
                        version INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_ID,))
                cursor.execute("SELECT version FROM schema_migration ORDER BY version")
                applied_versions = {row[0] for row in cursor.fetchall()}
                applied_now = []
                for migration in migrations:
                    if migration.version in applied_versions:
                        continue
                    cursor.execute(migration.sql)
                    cursor.execute(
                        "INSERT INTO schema_migration (version, name) VALUES (%s, %s)",
                        (migration.version, migration.name),
                    )
                    applied_now.append(migration.version)
        return applied_now


def load_migrations(path):
    migrations = []
    versions = set()
    for migration_path in sorted(Path(path).glob("*.sql")):
        match = MIGRATION_FILENAME.fullmatch(migration_path.name)
        if not match:
            continue
        version = int(match.group(1))
        if version in versions:
            raise ValueError(f"Duplicate migration version: {version:04d}")
        versions.add(version)
        migrations.append(Migration(version, match.group(2), migration_path.read_text()))
    if not migrations:
        raise ValueError("No versioned SQL migrations found")
    return migrations


def lambda_handler(event, context, secret_reader=None, migration_runner=None):
    del event, context
    try:
        migrations = load_migrations(
            os.environ.get("MIGRATIONS_PATH", str(Path(__file__).parent / "migrations"))
        )
        reader = secret_reader or SecretsManagerSecretReader()
        credentials = reader.get_database_credentials(os.environ["DATABASE_SECRET_ARN"])
        settings = DatabaseConnectionSettings(
            host=os.environ["DATABASE_HOST"],
            port=int(os.environ["DATABASE_PORT"]),
            dbname=os.environ["DATABASE_NAME"],
            username=credentials.username,
            password=credentials.password,
        )
        runner = migration_runner or PsycopgMigrationRunner()
        applied = runner.apply(settings, migrations)
    except Exception as error:
        LOGGER.error(
            json.dumps(
                {
                    "event": "database_migration",
                    "status": "error",
                    "error_type": type(error).__name__,
                }
            )
        )
        raise RuntimeError("Database migration failed") from None

    response = {
        "status": "ok",
        "applied": len(applied),
        "current_version": migrations[-1].version,
    }
    LOGGER.info(json.dumps({"event": "database_migration", **response}))
    return response
