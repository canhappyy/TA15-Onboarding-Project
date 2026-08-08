from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from src.clients.open_route_service import (
    OpenRouteServiceError,
    OpenRouteServiceGeocoder,
    OpenRouteServiceTimeout,
)
from src.common.geojson import geometry_bounds, load_geojson_geometry, point_in_geometry
from src.common.responses import error_response, success_response


logger = logging.getLogger("location_search")
BOUNDARY_PATH = Path(__file__).parent / "assets" / "city-of-melbourne-boundary-2022.geojson"
MAX_RESULTS = 5
UPSTREAM_RESULT_LIMIT = 10
_cached_boundary_geometry: dict[str, Any] | None = None


class SecretsManagerApiKeyReader:
    def __init__(self, client=None) -> None:
        if client is None:
            import boto3

            client = boto3.client("secretsmanager")
        self._client = client

    def get_api_key(self, secret_arn: str) -> str:
        response = self._client.get_secret_value(SecretId=secret_arn)
        secret_string = response.get("SecretString")
        if not isinstance(secret_string, str):
            raise ValueError("ORS secret has no SecretString")

        try:
            secret = json.loads(secret_string)
        except json.JSONDecodeError as error:
            raise ValueError("ORS secret must be JSON") from error

        api_key = secret.get("api_key") if isinstance(secret, dict) else None
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("ORS secret is missing api_key")
        return api_key.strip()


def lambda_handler(
    event,
    context,
    *,
    secret_reader=None,
    geocoder=None,
    boundary_geometry=None,
):
    text = ((event.get("queryStringParameters") or {}).get("text") or "").strip()
    if not text:
        return error_response(400, "INVALID_REQUEST", "Search text is required.")

    secret_arn = os.environ.get("ORS_API_KEY_SECRET_ARN")
    if not secret_arn:
        logger.error("Location search configuration is unavailable")
        return _configuration_error()

    try:
        api_key = (secret_reader or SecretsManagerApiKeyReader()).get_api_key(secret_arn)
        boundary = boundary_geometry or _get_boundary_geometry()
        bounds = geometry_bounds(boundary)
        location_geocoder = geocoder or OpenRouteServiceGeocoder(api_key)
        candidates = location_geocoder.search(
            text,
            bounds=bounds,
            limit=UPSTREAM_RESULT_LIMIT,
        )
    except OpenRouteServiceTimeout:
        return error_response(504, "UPSTREAM_TIMEOUT", "Location search provider timed out.")
    except OpenRouteServiceError:
        return error_response(502, "UPSTREAM_ERROR", "Location search provider returned an invalid response.")
    except Exception as error:
        logger.error(
            "Location search configuration failed",
            extra={"error_type": type(error).__name__},
        )
        return _configuration_error()

    suggestions = [
        candidate
        for candidate in candidates
        if point_in_geometry(
            candidate["coordinates"]["longitude"],
            candidate["coordinates"]["latitude"],
            boundary,
        )
    ][:MAX_RESULTS]

    if candidates and not suggestions:
        return error_response(
            400,
            "OUTSIDE_SERVICE_AREA",
            "No matching locations were found within the City of Melbourne.",
        )
    return success_response({"suggestions": suggestions})


def _get_boundary_geometry() -> dict[str, Any]:
    global _cached_boundary_geometry
    if _cached_boundary_geometry is None:
        _cached_boundary_geometry = load_geojson_geometry(BOUNDARY_PATH)
    return _cached_boundary_geometry


def _configuration_error():
    return error_response(
        500,
        "INTERNAL_SERVER_ERROR",
        "Location search is temporarily unavailable.",
    )
