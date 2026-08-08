"""AWS adapter for scheduled City of Melbourne Open Data ingestion."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from src.clients.open_data_sync import OpenDataSyncClient
from src.ingestion.service import IngestionService, SUPPORTED_MODES


LOGGER = logging.getLogger("ingestion")
LOGGER.setLevel(logging.INFO)


@dataclass(frozen=True)
class DatabaseCredentials:
    username: str
    password: str


@dataclass(frozen=True)
class DatabaseConnectionSettings:
    host: str
    port: int
    dbname: str
    username: str
    password: str


class SecretsManagerSecretReader:
    def __init__(self, client: Any = None) -> None:
        if client is None:
            import boto3

            client = boto3.client("secretsmanager")
        self._client = client

    def get_database_credentials(self, secret_arn: str) -> DatabaseCredentials:
        response = self._client.get_secret_value(SecretId=secret_arn)
        payload = json.loads(response["SecretString"])
        if not isinstance(payload, dict) or any(
            key not in payload for key in ("username", "password")
        ):
            raise ValueError("RDS-managed secret is missing required credentials")
        return DatabaseCredentials(
            username=payload["username"],
            password=payload["password"],
        )


class PsycopgConnectionFactory:
    def __init__(self, settings: DatabaseConnectionSettings, *, connect: Any = None):
        if connect is None:
            from psycopg import connect

        self._settings = settings
        self._connect = connect

    def __call__(self) -> Any:
        return self._connect(
            host=self._settings.host,
            port=self._settings.port,
            dbname=self._settings.dbname,
            user=self._settings.username,
            password=self._settings.password,
            sslmode="require",
            connect_timeout=10,
        )


def build_service(
    *,
    secret_reader: Any = None,
    connect: Any = None,
    client: Any = None,
) -> IngestionService:
    reader = secret_reader or SecretsManagerSecretReader()
    credentials = reader.get_database_credentials(os.environ["DATABASE_SECRET_ARN"])
    settings = DatabaseConnectionSettings(
        host=os.environ["DATABASE_HOST"],
        port=int(os.environ["DATABASE_PORT"]),
        dbname=os.environ["DATABASE_NAME"],
        username=credentials.username,
        password=credentials.password,
    )
    return IngestionService(
        client=client or OpenDataSyncClient(),
        connection_factory=PsycopgConnectionFactory(settings, connect=connect),
    )


def lambda_handler(
    event: Any,
    context: Any,
    *,
    service: Any = None,
) -> dict[str, Any]:
    del context
    mode = event.get("mode") if isinstance(event, dict) else None

    try:
        if mode not in SUPPORTED_MODES:
            raise ValueError("Unsupported ingestion mode")
        result = (service or build_service()).run(mode)
    except Exception as error:
        LOGGER.error(
            json.dumps(
                {
                    "event": "open_data_ingestion",
                    "status": "error",
                    "mode": mode if isinstance(mode, str) else "unknown",
                    "error_type": type(error).__name__,
                }
            )
        )
        raise RuntimeError("Ingestion failed") from None

    LOGGER.info(
        json.dumps(
            {
                "event": "open_data_ingestion",
                "status": "ok",
                "mode": mode,
                "datasets": result.get("datasets", {}),
            }
        )
    )
    return result
