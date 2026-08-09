import json
import os
from unittest.mock import patch

import pytest

from src.functions.ingestion.handler import (
    DatabaseConnectionSettings,
    DatabaseCredentials,
    PsycopgConnectionFactory,
    SecretsManagerSecretReader,
    build_service,
    lambda_handler,
)
from src.ingestion.service import IngestionService


class FakeService:
    def __init__(self, result=None, error=None):
        self.result = result or {
            "mode": "minute",
            "datasets": {
                "minute": {
                    "inserted": 2,
                    "updated": 1,
                    "rejected": 0,
                    "duplicates_resolved": 1,
                }
            },
        }
        self.error = error
        self.modes = []

    def run(self, mode):
        self.modes.append(mode)
        if self.error:
            raise self.error
        return self.result


class FakeSecretsClient:
    def __init__(self, payload):
        self.payload = payload
        self.secret_ids = []

    def get_secret_value(self, SecretId):
        self.secret_ids.append(SecretId)
        return {"SecretString": json.dumps(self.payload)}


class FakeSecretReader:
    def __init__(self, credentials):
        self.credentials = credentials
        self.secret_arns = []

    def get_database_credentials(self, secret_arn):
        self.secret_arns.append(secret_arn)
        return self.credentials


@pytest.mark.parametrize(
    "mode", ["bootstrap", "minute", "hourly", "static", "status"]
)
def test_handler_runs_supported_mode_and_returns_sanitized_statistics(mode):
    service = FakeService(
        result={"mode": mode, "datasets": {"minute": {"inserted": 2}}}
    )

    result = lambda_handler({"mode": mode}, None, service=service)

    assert service.modes == [mode]
    assert result == {"mode": mode, "datasets": {"minute": {"inserted": 2}}}


def test_handler_returns_status_shape_without_requiring_dataset_statistics():
    status = {
        "mode": "status",
        "tables": {"sensors": {"rows": 1, "active_with_coordinates": 1}},
        "checkpoints": {"sensors": {}},
    }

    result = lambda_handler(
        {"mode": "status"},
        None,
        service=FakeService(result=status),
    )

    assert result == status


@pytest.mark.parametrize("mode", ["minute", "bootstrap"])
def test_successful_minute_work_emits_exact_freshness_metrics(
    mode, caplog, monkeypatch
):
    monkeypatch.setenv("METRIC_NAMESPACE", "ClearWay/Ingestion")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    result = {
        "mode": mode,
        "datasets": {"minute": {"inserted": 2}},
        "freshness": {
            "minute": {
                "observedAt": "2026-08-09T10:15:00+10:00",
                "ageSeconds": 300,
                "stale": False,
                "thresholdSeconds": 2700,
            }
        },
    }

    with caplog.at_level("INFO", logger="ingestion"):
        lambda_handler({"mode": mode}, None, service=FakeService(result=result))

    metric = next(
        json.loads(record.message)
        for record in caplog.records
        if "MinuteDataFresh" in record.message
    )
    assert metric["event"] == "pedestrian_minute_freshness"
    assert metric["mode"] == mode
    assert metric["Environment"] == "dev"
    assert metric["MinuteDataFresh"] == 1
    assert metric["MinuteDataAgeSeconds"] == 300
    assert metric["_aws"]["CloudWatchMetrics"] == [
        {
            "Namespace": "ClearWay/Ingestion",
            "Dimensions": [["Environment"]],
            "Metrics": [
                {"Name": "MinuteDataFresh", "Unit": "Count"},
                {"Name": "MinuteDataAgeSeconds", "Unit": "Seconds"},
            ],
        }
    ]


def test_missing_observation_emits_stale_gauge_without_age_metric(
    caplog, monkeypatch
):
    monkeypatch.setenv("METRIC_NAMESPACE", "ClearWay/Ingestion")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    result = {
        "mode": "minute",
        "datasets": {"minute": {"inserted": 0}},
        "freshness": {
            "minute": {
                "observedAt": None,
                "ageSeconds": None,
                "stale": True,
                "thresholdSeconds": 2700,
            }
        },
    }

    with caplog.at_level("INFO", logger="ingestion"):
        lambda_handler(
            {"mode": "minute"}, None, service=FakeService(result=result)
        )

    metric = next(
        json.loads(record.message)
        for record in caplog.records
        if "MinuteDataFresh" in record.message
    )
    assert metric["MinuteDataFresh"] == 0
    assert "MinuteDataAgeSeconds" not in metric
    assert metric["_aws"]["CloudWatchMetrics"][0]["Metrics"] == [
        {"Name": "MinuteDataFresh", "Unit": "Count"}
    ]


@pytest.mark.parametrize(
    ("mode", "result"),
    [
        ("status", {"mode": "status", "freshness": {"minute": {}}}),
        ("hourly", {"mode": "hourly", "datasets": {"hourly": {}}}),
        (
            "minute",
            {
                "mode": "minute",
                "status": "skipped",
                "reason": "INGESTION_ALREADY_RUNNING",
                "datasets": {},
            },
        ),
    ],
)
def test_non_ingesting_results_do_not_emit_freshness_metrics(
    mode, result, caplog
):
    with caplog.at_level("INFO", logger="ingestion"):
        lambda_handler({"mode": mode}, None, service=FakeService(result=result))

    assert all("MinuteDataFresh" not in record.message for record in caplog.records)


@pytest.mark.parametrize("event", [None, {}, {"mode": None}, {"mode": "all"}])
def test_handler_rejects_invalid_events(event):
    with pytest.raises(RuntimeError, match="Ingestion failed"):
        lambda_handler(event, None, service=FakeService())


def test_handler_failure_log_is_sanitized(caplog):
    service = FakeService(
        error=ValueError("password-value -37.8100 144.9600 private-record")
    )

    with caplog.at_level("ERROR", logger="ingestion"):
        with pytest.raises(RuntimeError, match="Ingestion failed"):
            lambda_handler({"mode": "minute"}, None, service=service)

    output = caplog.text
    assert "ValueError" in output
    for private_value in (
        "password-value",
        "-37.8100",
        "144.9600",
        "private-record",
    ):
        assert private_value not in output


def test_secret_reader_accepts_rds_managed_username_and_password():
    client = FakeSecretsClient(
        {"username": "clearway_admin", "password": "secret-value"}
    )

    credentials = SecretsManagerSecretReader(client).get_database_credentials(
        "secret-arn"
    )

    assert credentials == DatabaseCredentials("clearway_admin", "secret-value")
    assert client.secret_ids == ["secret-arn"]


def test_secret_reader_rejects_missing_credentials():
    reader = SecretsManagerSecretReader(FakeSecretsClient({"username": "admin"}))

    with pytest.raises(ValueError, match="missing required credentials"):
        reader.get_database_credentials("secret-arn")


def test_connection_factory_uses_tls_and_never_connects_until_called():
    calls = []
    sentinel = object()

    def connect(**kwargs):
        calls.append(kwargs)
        return sentinel

    factory = PsycopgConnectionFactory(
        DatabaseConnectionSettings(
            host="private.example.internal",
            port=5432,
            dbname="clearway",
            username="clearway_admin",
            password="secret-value",
        ),
        connect=connect,
    )

    assert calls == []
    assert factory() is sentinel
    assert calls == [
        {
            "host": "private.example.internal",
            "port": 5432,
            "dbname": "clearway",
            "user": "clearway_admin",
            "password": "secret-value",
            "sslmode": "require",
            "connect_timeout": 10,
        }
    ]


def test_build_service_reads_environment_and_managed_secret():
    credentials = DatabaseCredentials("clearway_admin", "secret-value")
    reader = FakeSecretReader(credentials)
    environment = {
        "DATABASE_HOST": "private.example.internal",
        "DATABASE_PORT": "5432",
        "DATABASE_NAME": "clearway",
        "DATABASE_SECRET_ARN": "secret-arn",
    }

    with patch.dict(os.environ, environment, clear=True):
        service = build_service(
            secret_reader=reader,
            connect=lambda **_kwargs: None,
            client=object(),
        )

    assert isinstance(service, IngestionService)
    assert reader.secret_arns == ["secret-arn"]
