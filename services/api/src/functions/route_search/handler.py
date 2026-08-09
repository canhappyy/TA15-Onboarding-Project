"""API Gateway handler for sensory-aware walking route search."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
from typing import Any

from src.clients.open_route_service import (
    OpenRouteServiceError,
    OpenRouteServiceDirections,
    OpenRouteServiceNotFound,
    OpenRouteServiceTimeout,
)
from src.common.geojson import load_geojson_geometry, point_in_geometry
from src.common.responses import error_response, success_response
from src.repositories.api import PostgresApiRepository
from src.services.route_search import RouteSearchDataUnavailable, RouteSearchService


LOGGER = logging.getLogger("route_search")
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


class PsycopgRouteSearchRuntime:
    def __init__(
        self,
        *,
        settings,
        ors_secret_arn,
        database_secret_arn,
        boundary_geometry,
        secret_reader=None,
        connect=None,
        directions_factory=OpenRouteServiceDirections,
        repository_factory=PostgresApiRepository,
        service_factory=RouteSearchService,
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
        self._boundary = boundary_geometry
        self._secret_reader = secret_reader or SecretsManagerReader()
        self._connect = connect
        self._directions_factory = directions_factory
        self._repository_factory = repository_factory
        self._service_factory = service_factory
        self._database_errors = database_errors

    def search(self, origin, destination, *, reference_time):
        api_key = self._secret_reader.get_ors_api_key(self._ors_secret_arn)
        username, password = self._secret_reader.get_database_credentials(
            self._database_secret_arn
        )
        directions = self._directions_factory(api_key)
        data_loader = PsycopgRouteDataLoader(
            settings=self._settings,
            username=username,
            password=password,
            connect=self._connect,
            repository_factory=self._repository_factory,
            database_errors=self._database_errors,
        )
        service = self._service_factory(
            directions,
            data_loader,
            self._boundary,
        )
        return service.search(
            origin,
            destination,
            reference_time=reference_time,
        )


class PsycopgRouteDataLoader:
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

    def load(self, reference_time, bounds=None):
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
                    sensors = repository.list_sensor_conditions(
                        reference_time,
                        bounds,
                    )
                    refuges = repository.list_refuges(bounds)
                    return sensors, refuges
        except self._database_errors as error:
            raise RouteSearchDataUnavailable(
                "PostgreSQL route data is unavailable"
            ) from error


def lambda_handler(
    event,
    context,
    *,
    service=None,
    boundary_geometry=None,
    clock=None,
):
    del context
    try:
        origin, destination = _parse_request(event)
    except ValueError:
        return error_response(400, "INVALID_REQUEST", "A valid journey is required.")

    try:
        boundary = boundary_geometry or _get_boundary()
    except Exception as error:
        LOGGER.error(
            "Route search boundary configuration failed",
            extra={"error_type": type(error).__name__},
        )
        return _internal_error()
    if not all(
        point_in_geometry(longitude, latitude, boundary)
        for longitude, latitude in (origin, destination)
    ):
        return error_response(
            400,
            "OUTSIDE_SERVICE_AREA",
            "Origin and destination must be within the City of Melbourne.",
        )

    try:
        route_service = service or _build_service(boundary)
        reference_time = (clock or _utc_now)()
        routes = route_service.search(
            origin,
            destination,
            reference_time=reference_time,
        )
    except OpenRouteServiceNotFound:
        return error_response(404, "NOT_FOUND", "No walking route was found.")
    except OpenRouteServiceTimeout:
        return error_response(504, "UPSTREAM_TIMEOUT", "Route provider timed out.")
    except OpenRouteServiceError:
        return error_response(
            502,
            "UPSTREAM_ERROR",
            "Route provider returned an invalid response.",
        )
    except RouteSearchDataUnavailable:
        return error_response(
            503,
            "DATA_UNAVAILABLE",
            "Sensory route data is temporarily unavailable.",
        )
    except Exception as error:
        LOGGER.error(
            "Route search failed",
            extra={"error_type": type(error).__name__},
        )
        return _internal_error()
    return success_response({"routes": routes})


def _parse_request(event):
    body = event.get("body") if isinstance(event, dict) else None
    if not isinstance(body, str):
        raise ValueError("body must be JSON")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise ValueError("body must be JSON") from error
    if not isinstance(payload, dict) or set(payload) != {"origin", "destination"}:
        raise ValueError("origin and destination are required")
    origin = _parse_coordinates(payload["origin"])
    destination = _parse_coordinates(payload["destination"])
    if origin == destination:
        raise ValueError("origin and destination must differ")
    return origin, destination


def _parse_coordinates(value):
    if not isinstance(value, dict) or set(value) != {"latitude", "longitude"}:
        raise ValueError("coordinates are invalid")
    latitude = value["latitude"]
    longitude = value["longitude"]
    if not _finite_number(latitude) or not _finite_number(longitude):
        raise ValueError("coordinates must be finite numbers")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("coordinates are outside global ranges")
    return float(longitude), float(latitude)


def _finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _get_boundary():
    global _cached_boundary
    if _cached_boundary is None:
        _cached_boundary = load_geojson_geometry(BOUNDARY_PATH)
    return _cached_boundary


def _utc_now():
    return datetime.now(timezone.utc)


def _build_service(boundary):
    return PsycopgRouteSearchRuntime(
        settings=DatabaseSettings(
            host=os.environ["DATABASE_HOST"],
            port=int(os.environ["DATABASE_PORT"]),
            dbname=os.environ["DATABASE_NAME"],
        ),
        ors_secret_arn=os.environ["ORS_API_KEY_SECRET_ARN"],
        database_secret_arn=os.environ["DATABASE_SECRET_ARN"],
        boundary_geometry=boundary,
    )


def _internal_error():
    return error_response(
        500,
        "INTERNAL_SERVER_ERROR",
        "Route search is temporarily unavailable.",
    )
