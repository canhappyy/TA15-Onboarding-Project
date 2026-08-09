"""API Gateway handler for nearby quiet-space refuges."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import math
import os
from pathlib import Path
from typing import Any

from src.clients.open_route_service import (
    OpenRouteServiceError,
    OpenRouteServiceMatrix,
    OpenRouteServiceTimeout,
)
from src.common.geojson import load_geojson_geometry, point_in_geometry
from src.common.responses import error_response, success_response
from src.repositories.api import BoundingBox, PostgresApiRepository, REFUGE_SUBTHEMES
from src.services.refuge_search import (
    EARTH_RADIUS_METRES,
    SEARCH_RADIUS_METRES,
    RefugeSearchDataUnavailable,
    RefugeSearchService,
)


LOGGER = logging.getLogger("refuge_search")
BOUNDARY_PATH = (
    Path(__file__).parents[1]
    / "location_search"
    / "assets"
    / "city-of-melbourne-boundary-2022.geojson"
)
_cached_boundary: dict[str, Any] | None = None


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    dbname: str


class SecretsManagerReader:
    def __init__(self, client=None):
        if client is None:
            import boto3

            client = boto3.client("secretsmanager")
        self._client = client

    def get_ors_api_key(self, secret_arn):
        payload = self._read_json(secret_arn)
        api_key = payload.get("api_key")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("ORS secret is missing api_key")
        return api_key.strip()

    def get_database_credentials(self, secret_arn):
        payload = self._read_json(secret_arn)
        username = payload.get("username")
        password = payload.get("password")
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Database secret is missing username")
        if not isinstance(password, str) or not password:
            raise ValueError("Database secret is missing password")
        return username.strip(), password

    def _read_json(self, secret_arn):
        response = self._client.get_secret_value(SecretId=secret_arn)
        secret_string = response.get("SecretString")
        if not isinstance(secret_string, str):
            raise ValueError("Secret has no SecretString")
        try:
            payload = json.loads(secret_string)
        except json.JSONDecodeError as error:
            raise ValueError("Secret must be JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("Secret must contain an object")
        return payload


class PsycopgRefugeSearchRuntime:
    def __init__(
        self,
        *,
        settings,
        ors_secret_arn,
        database_secret_arn,
        secret_reader=None,
        connect=None,
        matrix_factory=OpenRouteServiceMatrix,
        repository_factory=PostgresApiRepository,
        service_factory=RefugeSearchService,
        database_errors=None,
    ):
        if connect is None:
            from psycopg import connect
        if database_errors is None:
            from psycopg import Error

            database_errors = (Error,)
        self._settings = settings
        self._ors_secret_arn = ors_secret_arn
        self._database_secret_arn = database_secret_arn
        self._secret_reader = secret_reader or SecretsManagerReader()
        self._connect = connect
        self._matrix_factory = matrix_factory
        self._repository_factory = repository_factory
        self._service_factory = service_factory
        self._database_errors = database_errors

    def search(self, origin, category=None):
        api_key = self._secret_reader.get_ors_api_key(self._ors_secret_arn)
        username, password = self._secret_reader.get_database_credentials(
            self._database_secret_arn
        )
        loader = PsycopgRefugeDataLoader(
            settings=self._settings,
            username=username,
            password=password,
            connect=self._connect,
            repository_factory=self._repository_factory,
            database_errors=self._database_errors,
        )
        return self._service_factory(self._matrix_factory(api_key), loader).search(
            origin,
            category=category,
        )


class PsycopgRefugeDataLoader:
    def __init__(
        self,
        *,
        settings,
        username,
        password,
        connect,
        repository_factory=PostgresApiRepository,
        database_errors,
    ):
        self._settings = settings
        self._username = username
        self._password = password
        self._connect = connect
        self._repository_factory = repository_factory
        self._database_errors = database_errors

    def load(self, origin, category=None):
        try:
            with self._connect(
                host=self._settings.host,
                port=self._settings.port,
                dbname=self._settings.dbname,
                user=self._username,
                password=self._password,
                sslmode="require",
                connect_timeout=5,
            ) as connection:
                with connection.transaction():
                    connection.execute("SET TRANSACTION READ ONLY")
                    repository = self._repository_factory(connection)
                    return repository.list_refuges(
                        bounds=_search_bounds(origin),
                        categories=[category] if category else None,
                    )
        except self._database_errors as error:
            raise RefugeSearchDataUnavailable(
                "PostgreSQL refuge data is unavailable"
            ) from error


def lambda_handler(event, context, *, service=None, boundary_geometry=None):
    del context
    try:
        origin, category = _parse_request(event)
    except ValueError:
        return error_response(400, "INVALID_REQUEST", "A valid location is required.")

    try:
        boundary = boundary_geometry or _get_boundary()
    except Exception as error:
        LOGGER.error(
            "Refuge search boundary configuration failed",
            extra={"error_type": type(error).__name__},
        )
        return _internal_error()
    if not point_in_geometry(origin[0], origin[1], boundary):
        return error_response(
            400,
            "OUTSIDE_SERVICE_AREA",
            "Location must be within the City of Melbourne.",
        )

    try:
        refuges = (service or _build_service()).search(origin, category=category)
    except RefugeSearchDataUnavailable:
        return error_response(
            503,
            "DATA_UNAVAILABLE",
            "Quiet-space data is temporarily unavailable.",
        )
    except OpenRouteServiceTimeout:
        return error_response(504, "UPSTREAM_TIMEOUT", "Route provider timed out.")
    except OpenRouteServiceError:
        return error_response(
            502,
            "UPSTREAM_ERROR",
            "Route provider returned an invalid response.",
        )
    except Exception as error:
        LOGGER.error(
            "Refuge search failed",
            extra={"error_type": type(error).__name__},
        )
        return _internal_error()
    return success_response({"refuges": refuges})


def _parse_request(event):
    parameters = event.get("queryStringParameters") if isinstance(event, dict) else None
    if not isinstance(parameters, dict) or set(parameters) not in (
        {"latitude", "longitude"},
        {"latitude", "longitude", "category"},
    ):
        raise ValueError("latitude, longitude, and optional category are required")
    latitude = _parse_coordinate(parameters["latitude"], -90, 90)
    longitude = _parse_coordinate(parameters["longitude"], -180, 180)
    category = parameters.get("category")
    if category is not None and category not in REFUGE_SUBTHEMES:
        raise ValueError("category is unsupported")
    return (longitude, latitude), category


def _parse_coordinate(value, lower, upper):
    if not isinstance(value, str):
        raise ValueError("coordinate is invalid")
    try:
        coordinate = float(value)
    except ValueError as error:
        raise ValueError("coordinate is invalid") from error
    if not math.isfinite(coordinate) or not lower <= coordinate <= upper:
        raise ValueError("coordinate is invalid")
    return coordinate


def _search_bounds(origin):
    longitude, latitude = origin
    query_angular_radius = (SEARCH_RADIUS_METRES + 1) / EARTH_RADIUS_METRES
    latitude_delta = math.degrees(query_angular_radius)
    longitude_delta = math.degrees(
        math.asin(
            math.sin(query_angular_radius) / math.cos(math.radians(latitude))
        )
    )
    return BoundingBox(
        south=latitude - latitude_delta,
        west=longitude - longitude_delta,
        north=latitude + latitude_delta,
        east=longitude + longitude_delta,
    )


def _get_boundary():
    global _cached_boundary
    if _cached_boundary is None:
        _cached_boundary = load_geojson_geometry(BOUNDARY_PATH)
    return _cached_boundary


def _build_service():
    return PsycopgRefugeSearchRuntime(
        settings=DatabaseSettings(
            host=os.environ["DATABASE_HOST"],
            port=int(os.environ["DATABASE_PORT"]),
            dbname=os.environ["DATABASE_NAME"],
        ),
        ors_secret_arn=os.environ["ORS_API_KEY_SECRET_ARN"],
        database_secret_arn=os.environ["DATABASE_SECRET_ARN"],
    )


def _internal_error():
    return error_response(
        500,
        "INTERNAL_SERVER_ERROR",
        "Quiet-space search is temporarily unavailable.",
    )
