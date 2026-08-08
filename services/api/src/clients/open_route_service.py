from __future__ import annotations

import json
import socket
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GEOCODING_URL = "https://api.heigit.org/pelias/v1/search"
REQUEST_TIMEOUT_SECONDS = 5


class OpenRouteServiceError(Exception):
    """Raised when ORS fails or returns an unusable response."""


class OpenRouteServiceTimeout(OpenRouteServiceError):
    """Raised when ORS does not respond before the configured timeout."""


def _request_json(url: str, params: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = Request(
        f"{url}?{urlencode(params)}",
        headers={"Accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout) as error:
        raise OpenRouteServiceTimeout("OpenRouteService request timed out") from error
    except HTTPError as error:
        raise OpenRouteServiceError("OpenRouteService returned an HTTP error") from error
    except URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise OpenRouteServiceTimeout("OpenRouteService request timed out") from error
        raise OpenRouteServiceError("OpenRouteService request failed") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OpenRouteServiceError("OpenRouteService returned malformed JSON") from error

    if not isinstance(payload, dict):
        raise OpenRouteServiceError("OpenRouteService returned a malformed response")
    return payload


class OpenRouteServiceGeocoder:
    def __init__(
        self,
        api_key: str,
        *,
        request_json: Callable[[str, dict[str, Any], int], dict[str, Any]] = _request_json,
    ) -> None:
        self._api_key = api_key
        self._request_json = request_json

    def search(
        self,
        text: str,
        *,
        bounds: tuple[float, float, float, float],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        min_lon, min_lat, max_lon, max_lat = bounds
        params = {
            "api_key": self._api_key,
            "text": text,
            "size": limit,
            "boundary.rect.min_lon": min_lon,
            "boundary.rect.min_lat": min_lat,
            "boundary.rect.max_lon": max_lon,
            "boundary.rect.max_lat": max_lat,
        }

        try:
            payload = self._request_json(
                GEOCODING_URL,
                params,
                REQUEST_TIMEOUT_SECONDS,
            )
        except OpenRouteServiceError:
            raise
        except (TimeoutError, socket.timeout) as error:
            raise OpenRouteServiceTimeout("OpenRouteService request timed out") from error
        except Exception as error:
            raise OpenRouteServiceError("OpenRouteService request failed") from error

        features = payload.get("features")
        if not isinstance(features, list):
            raise OpenRouteServiceError("OpenRouteService returned a malformed response")

        return [self._parse_feature(feature) for feature in features]

    @staticmethod
    def _parse_feature(feature: Any) -> dict[str, Any]:
        if not isinstance(feature, dict):
            raise OpenRouteServiceError("OpenRouteService returned a malformed feature")

        geometry = feature.get("geometry")
        properties = feature.get("properties")
        if not isinstance(geometry, dict) or not isinstance(properties, dict):
            raise OpenRouteServiceError("OpenRouteService returned a malformed feature")

        coordinates = geometry.get("coordinates")
        label = properties.get("label")
        identifier = properties.get("gid") or properties.get("id") or feature.get("id")
        if (
            geometry.get("type") != "Point"
            or not isinstance(coordinates, list)
            or len(coordinates) < 2
            or not all(isinstance(value, (int, float)) for value in coordinates[:2])
            or not isinstance(label, str)
            or not label.strip()
            or identifier is None
        ):
            raise OpenRouteServiceError("OpenRouteService returned a malformed feature")

        longitude, latitude = coordinates[:2]
        return {
            "id": str(identifier),
            "label": label,
            "coordinates": {
                "latitude": latitude,
                "longitude": longitude,
            },
        }
