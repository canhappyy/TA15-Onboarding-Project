from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.clients.open_route_service import (
    OpenRouteServiceError,
    OpenRouteServiceNotFound,
    OpenRouteServiceTimeout,
)
from src.functions.route_search.handler import (
    DatabaseSettings,
    PsycopgRouteDataLoader,
    PsycopgRouteSearchRuntime,
    SecretsManagerReader,
    lambda_handler,
)
from src.services.route_search import RouteSearchDataUnavailable


BOUNDARY = {
    "type": "Polygon",
    "coordinates": [
        [[144.90, -37.86], [145.00, -37.86], [145.00, -37.77], [144.90, -37.77], [144.90, -37.86]]
    ],
}
ORIGIN = {"latitude": -37.82, "longitude": 144.95}
DESTINATION = {"latitude": -37.80, "longitude": 144.97}
NOW = datetime(2026, 8, 9, 2, 0, tzinfo=timezone.utc)


class FakeService:
    def __init__(self, routes=None, error=None):
        self.routes = routes or [{"id": "route-1"}, {"id": "route-2"}]
        self.error = error
        self.calls = []

    def search(self, origin, destination, *, reference_time):
        self.calls.append((origin, destination, reference_time))
        if self.error:
            raise self.error
        return self.routes


def event(body):
    return {"version": "2.0", "body": body}


def invoke(body, *, service=None, boundary=BOUNDARY):
    return lambda_handler(
        event(body),
        None,
        service=service or FakeService(),
        boundary_geometry=boundary,
        clock=lambda: NOW,
    )


def decode(response):
    return response["statusCode"], json.loads(response["body"])


def test_handler_returns_common_success_envelope():
    service = FakeService()
    status, body = decode(
        invoke(
            json.dumps({"origin": ORIGIN, "destination": DESTINATION}),
            service=service,
        )
    )

    assert status == 200
    assert body == {
        "success": True,
        "data": {"routes": [{"id": "route-1"}, {"id": "route-2"}]},
    }
    assert service.calls == [
        ((144.95, -37.82), (144.97, -37.80), NOW),
    ]


@pytest.mark.parametrize(
    "body",
    [
        None,
        "not-json",
        "[]",
        "{}",
        json.dumps({"origin": ORIGIN, "destination": DESTINATION, "extra": True}),
        json.dumps({"origin": ORIGIN}),
        json.dumps({"origin": {"latitude": "bad", "longitude": 144.95}, "destination": DESTINATION}),
        json.dumps({"origin": {"latitude": float("nan"), "longitude": 144.95}, "destination": DESTINATION}),
        json.dumps({"origin": {"latitude": -91, "longitude": 144.95}, "destination": DESTINATION}),
        json.dumps({"origin": ORIGIN, "destination": ORIGIN}),
    ],
)
def test_handler_rejects_invalid_request_without_calling_service(body):
    service = FakeService()

    status, response_body = decode(invoke(body, service=service))

    assert status == 400
    assert response_body["error"]["code"] == "INVALID_REQUEST"
    assert service.calls == []


def test_handler_rejects_coordinate_outside_boundary():
    outside = {"latitude": -37.90, "longitude": 144.95}

    status, body = decode(
        invoke(json.dumps({"origin": outside, "destination": DESTINATION}))
    )

    assert status == 400
    assert body["error"]["code"] == "OUTSIDE_SERVICE_AREA"


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (OpenRouteServiceNotFound("none"), 404, "NOT_FOUND"),
        (OpenRouteServiceTimeout("timeout"), 504, "UPSTREAM_TIMEOUT"),
        (OpenRouteServiceError("bad"), 502, "UPSTREAM_ERROR"),
        (RouteSearchDataUnavailable("data"), 503, "DATA_UNAVAILABLE"),
    ],
)
def test_handler_maps_service_errors(error, status, code):
    response_status, body = decode(
        invoke(
            json.dumps({"origin": ORIGIN, "destination": DESTINATION}),
            service=FakeService(error=error),
        )
    )

    assert response_status == status
    assert body["error"]["code"] == code


class FakeSecretsClient:
    def __init__(self, values):
        self.values = values

    def get_secret_value(self, SecretId):
        return {"SecretString": self.values[SecretId]}


def test_secret_reader_reads_separate_ors_and_database_secrets():
    reader = SecretsManagerReader(
        client=FakeSecretsClient(
            {
                "ors": '{"api_key":"ors-key"}',
                "database": '{"username":"clearway_route_api","password":"db-pass"}',
            }
        )
    )

    assert reader.get_ors_api_key("ors") == "ors-key"
    assert reader.get_database_credentials("database") == (
        "clearway_route_api",
        "db-pass",
    )


class Context:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeConnection:
    def __init__(self):
        self.statements = []

    def transaction(self):
        return Context(None)

    def execute(self, statement):
        self.statements.append(statement)


def test_runtime_connects_with_tls_and_uses_read_only_transaction():
    connection = FakeConnection()
    connect_calls = []

    def connect(**kwargs):
        connect_calls.append(kwargs)
        return Context(connection)

    repository = FakeRepositoryRuntime()
    loader = PsycopgRouteDataLoader(
        settings=DatabaseSettings("db.internal", 5432, "clearway"),
        username="reader",
        password="db-pass",
        connect=connect,
        repository_factory=lambda database_connection: repository,
        database_errors=(RuntimeError,),
    )

    result = loader.load(NOW)

    assert result == ([], [])
    assert connect_calls == [
        {
            "host": "db.internal",
            "port": 5432,
            "dbname": "clearway",
            "user": "reader",
            "password": "db-pass",
            "sslmode": "require",
            "connect_timeout": 5,
        }
    ]
    assert connection.statements == ["SET TRANSACTION READ ONLY"]


def test_runtime_maps_only_database_driver_errors_to_data_unavailable():
    class DatabaseError(Exception):
        pass

    def connect(**kwargs):
        raise DatabaseError("database unavailable")

    runtime = PsycopgRouteSearchRuntime(
        settings=DatabaseSettings("db.internal", 5432, "clearway"),
        ors_secret_arn="ors",
        database_secret_arn="database",
        boundary_geometry=BOUNDARY,
        secret_reader=SecretsManagerReader(
            client=FakeSecretsClient(
                {
                    "ors": '{"api_key":"ors-key"}',
                    "database": '{"username":"reader","password":"db-pass"}',
                }
            )
        ),
        connect=connect,
        database_errors=(DatabaseError,),
        directions_factory=lambda api_key: FakeDirectionsRuntime(),
    )

    with pytest.raises(RouteSearchDataUnavailable):
        runtime.search(ORIGIN, DESTINATION, reference_time=NOW)


class FakeDirectionsRuntime:
    def alternatives(self, *, origin, destination):
        return []


def test_runtime_does_not_hold_database_connection_during_route_service_work():
    state = {"connection_open": False}

    class TrackingConnection(FakeConnection):
        def __enter__(self):
            state["connection_open"] = True
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            state["connection_open"] = False
            return False

    connection = TrackingConnection()

    def service_factory(directions, data_loader, boundary):
        assert state["connection_open"] is False

        class Service:
            def search(self, origin, destination, *, reference_time):
                data_loader.load(reference_time)
                assert state["connection_open"] is False
                return [{"id": "route-1"}, {"id": "route-2"}]

        return Service()

    runtime = PsycopgRouteSearchRuntime(
        settings=DatabaseSettings("db.internal", 5432, "clearway"),
        ors_secret_arn="ors",
        database_secret_arn="database",
        boundary_geometry=BOUNDARY,
        secret_reader=SecretsManagerReader(
            client=FakeSecretsClient(
                {
                    "ors": '{"api_key":"ors-key"}',
                    "database": '{"username":"reader","password":"db-pass"}',
                }
            )
        ),
        connect=lambda **kwargs: connection,
        directions_factory=lambda api_key: FakeDirectionsRuntime(),
        repository_factory=lambda database_connection: FakeRepositoryRuntime(),
        service_factory=service_factory,
        database_errors=(RuntimeError,),
    )

    runtime.search(ORIGIN, DESTINATION, reference_time=NOW)

    assert connection.statements == ["SET TRANSACTION READ ONLY"]


class FakeRepositoryRuntime:
    def list_sensor_conditions(self, reference_time, bounds=None):
        return []

    def list_refuges(self, bounds=None, categories=None):
        return []
