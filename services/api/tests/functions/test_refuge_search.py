from __future__ import annotations

import json
import math

import pytest

from src.clients.open_route_service import OpenRouteServiceError, OpenRouteServiceTimeout
from src.functions.refuge_search.handler import (
    DatabaseSettings,
    PsycopgRefugeDataLoader,
    PsycopgRefugeSearchRuntime,
    SecretsManagerReader,
    _search_bounds,
    lambda_handler,
)
from src.repositories.api import BoundingBox
from src.services.refuge_search import RefugeSearchDataUnavailable


BOUNDARY = {
    "type": "Polygon",
    "coordinates": [
        [
            [144.90, -37.86],
            [145.00, -37.86],
            [145.00, -37.77],
            [144.90, -37.77],
            [144.90, -37.86],
        ]
    ],
}
PARAMETERS = {"latitude": "-37.8136", "longitude": "144.9631"}


class FakeService:
    def __init__(self, refuges=None, error=None):
        self.refuges = refuges if refuges is not None else [{"id": "refuge-1"}]
        self.error = error
        self.calls = []

    def search(self, origin, category=None):
        self.calls.append((origin, category))
        if self.error:
            raise self.error
        return self.refuges


def invoke(parameters, *, service=None, boundary=BOUNDARY):
    return lambda_handler(
        {"version": "2.0", "queryStringParameters": parameters},
        None,
        service=service or FakeService(),
        boundary_geometry=boundary,
    )


def decode(response):
    return response["statusCode"], json.loads(response["body"])


def test_handler_returns_refuges_in_common_envelope():
    service = FakeService()

    status, body = decode(invoke(PARAMETERS, service=service))

    assert status == 200
    assert body == {"success": True, "data": {"refuges": [{"id": "refuge-1"}]}}
    assert service.calls == [((144.9631, -37.8136), None)]


@pytest.mark.parametrize(
    "parameters",
    [
        None,
        {},
        {"latitude": "-37.8136"},
        {"latitude": "-37.8136", "longitude": "144.9631", "extra": "x"},
        {"latitude": "nan", "longitude": "144.9631"},
        {"latitude": "-91", "longitude": "144.9631"},
        {"latitude": "-37.8136", "longitude": "144.9631", "category": "CAFE"},
        {"latitude": "-37.8136", "longitude": "144.9631", "category": "park"},
    ],
)
def test_handler_rejects_missing_invalid_or_extra_query_parameters(parameters):
    service = FakeService()

    status, body = decode(invoke(parameters, service=service))

    assert status == 400
    assert body["error"]["code"] == "INVALID_REQUEST"
    assert service.calls == []


@pytest.mark.parametrize("category", ["LIBRARY", "MUSEUM", "GARDEN", "PARK"])
def test_handler_passes_supported_category_to_service(category):
    service = FakeService()

    status, _ = decode(invoke({**PARAMETERS, "category": category}, service=service))

    assert status == 200
    assert service.calls == [((144.9631, -37.8136), category)]


def test_handler_rejects_origin_outside_city_boundary_without_calling_service():
    service = FakeService()

    status, body = decode(
        invoke({"latitude": "-37.90", "longitude": "144.9631"}, service=service)
    )

    assert status == 400
    assert body["error"]["code"] == "OUTSIDE_SERVICE_AREA"
    assert service.calls == []


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (RefugeSearchDataUnavailable("db"), 503, "DATA_UNAVAILABLE"),
        (OpenRouteServiceTimeout("timeout"), 504, "UPSTREAM_TIMEOUT"),
        (OpenRouteServiceError("upstream"), 502, "UPSTREAM_ERROR"),
    ],
)
def test_handler_maps_dependency_errors(error, status, code):
    response_status, body = decode(invoke(PARAMETERS, service=FakeService(error=error)))

    assert response_status == status
    assert body["error"]["code"] == code


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


class FakeRepository:
    def __init__(self):
        self.calls = []

    def list_refuges(self, bounds=None, categories=None):
        self.calls.append((bounds, categories))
        return []


def test_data_loader_uses_tls_read_only_database_connection_and_category():
    connection = FakeConnection()
    repository = FakeRepository()
    connect_calls = []

    def connect(**kwargs):
        connect_calls.append(kwargs)
        return Context(connection)

    loader = PsycopgRefugeDataLoader(
        settings=DatabaseSettings("db.internal", 5432, "clearway"),
        username="reader",
        password="db-pass",
        connect=connect,
        repository_factory=lambda database_connection: repository,
        database_errors=(RuntimeError,),
    )

    assert loader.load((144.9631, -37.8136), "PARK") == []
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
    assert repository.calls[0][1] == ["PARK"]


def test_data_loader_reuses_read_only_connection_for_route_bounds_and_categories():
    connection = FakeConnection()
    repository = FakeRepository()
    connect_calls = []

    def connect(**kwargs):
        connect_calls.append(kwargs)
        return Context(connection)

    loader = PsycopgRefugeDataLoader(
        settings=DatabaseSettings("db.internal", 5432, "clearway"),
        username="reader",
        password="db-pass",
        connect=connect,
        repository_factory=lambda database_connection: repository,
        database_errors=(RuntimeError,),
    )
    bounds = BoundingBox(-37.82, 144.95, -37.80, 144.98)

    assert loader.load_for_route(
        bounds=bounds,
        categories=("LIBRARY", "PARK"),
    ) == []

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
    assert repository.calls == [(bounds, ("LIBRARY", "PARK"))]


def test_database_bounds_include_candidates_exactly_one_kilometre_away():
    longitude, latitude = 144.9631, -37.8136
    angular_radius = 1_000 / 6_371_000
    north = latitude + math.degrees(angular_radius)
    east = longitude + math.degrees(
        math.asin(math.sin(angular_radius) / math.cos(math.radians(latitude)))
    )

    bounds = _search_bounds((longitude, latitude))

    assert bounds.north >= north
    assert bounds.east >= east


def test_runtime_maps_only_database_driver_errors_to_data_unavailable():
    class DatabaseError(Exception):
        pass

    class SecretReader:
        def get_ors_api_key(self, secret_arn):
            return "ors-key"

        def get_database_credentials(self, secret_arn):
            return "reader", "db-pass"

    runtime = PsycopgRefugeSearchRuntime(
        settings=DatabaseSettings("db.internal", 5432, "clearway"),
        ors_secret_arn="ors",
        database_secret_arn="database",
        secret_reader=SecretReader(),
        connect=lambda **kwargs: (_ for _ in ()).throw(DatabaseError("down")),
        database_errors=(DatabaseError,),
    )

    with pytest.raises(RefugeSearchDataUnavailable):
        runtime.search((144.9631, -37.8136))


def test_secret_reader_reads_reused_ors_and_read_only_database_secrets():
    class FakeSecretsClient:
        def get_secret_value(self, SecretId):
            return {
                "SecretString": {
                    "ors": '{"api_key":"ors-key"}',
                    "database": '{"username":"reader","password":"db-pass"}',
                }[SecretId]
            }

    reader = SecretsManagerReader(client=FakeSecretsClient())

    assert reader.get_ors_api_key("ors") == "ors-key"
    assert reader.get_database_credentials("database") == ("reader", "db-pass")
