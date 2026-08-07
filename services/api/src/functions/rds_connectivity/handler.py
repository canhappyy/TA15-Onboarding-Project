import json
import logging
import os
from dataclasses import dataclass


LOGGER = logging.getLogger("rds_connectivity")
LOGGER.setLevel(logging.INFO)


@dataclass(frozen=True)
class DatabaseConnectionSettings:
    host: str
    port: int
    dbname: str
    username: str
    password: str


@dataclass(frozen=True)
class DatabaseCredentials:
    username: str
    password: str


class SecretsManagerSecretReader:
    def __init__(self, client=None):
        if client is None:
            import boto3

            client = boto3.client("secretsmanager")
        self._client = client

    def get_database_credentials(self, secret_arn):
        response = self._client.get_secret_value(SecretId=secret_arn)
        payload = json.loads(response["SecretString"])
        required_keys = ("username", "password")
        if any(key not in payload for key in required_keys):
            raise ValueError("RDS-managed secret is missing required credentials")

        return DatabaseCredentials(
            username=payload["username"],
            password=payload["password"],
        )


class PsycopgDatabaseProbe:
    def __init__(self, connect=None):
        if connect is None:
            from psycopg import connect

        self._connect = connect

    def check(self, settings):
        with self._connect(
            host=settings.host,
            port=settings.port,
            dbname=settings.dbname,
            user=settings.username,
            password=settings.password,
            sslmode="require",
            connect_timeout=5,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    raise RuntimeError("Database probe returned an unexpected result")


def lambda_handler(event, context, secret_reader=None, database_probe=None):
    del event, context

    try:
        secret_arn = os.environ["DATABASE_SECRET_ARN"]
        reader = secret_reader or SecretsManagerSecretReader()
        probe = database_probe or PsycopgDatabaseProbe()
        credentials = reader.get_database_credentials(secret_arn)
        settings = DatabaseConnectionSettings(
            host=os.environ["DATABASE_HOST"],
            port=int(os.environ["DATABASE_PORT"]),
            dbname=os.environ["DATABASE_NAME"],
            username=credentials.username,
            password=credentials.password,
        )
        probe.check(settings)
    except Exception as error:
        LOGGER.error(
            json.dumps(
                {
                    "event": "rds_connectivity_check",
                    "status": "error",
                    "error_type": type(error).__name__,
                }
            )
        )
        raise RuntimeError("RDS connectivity check failed") from None

    LOGGER.info(json.dumps({"event": "rds_connectivity_check", "status": "ok"}))
    return {"status": "ok"}
