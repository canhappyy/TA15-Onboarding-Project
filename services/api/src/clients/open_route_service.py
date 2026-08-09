from __future__ import annotations

import json
import math
import socket
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GEOCODING_URL = "https://api.heigit.org/pelias/v1/search"
DIRECTION_URL = "https://api.openrouteservice.org/v2/directions/foot-walking/geojson"
MATRIX_URL = "https://api.openrouteservice.org/v2/matrix/foot-walking"
REQUEST_TIMEOUT_SECONDS = 5


class OpenRouteServiceError(Exception):
    """Raised when ORS fails or returns an unusable response."""


class OpenRouteServiceTimeout(OpenRouteServiceError):
    """Raised when ORS does not respond before the configured timeout."""


class OpenRouteServiceNotFound(OpenRouteServiceError):
    """Raised when ORS cannot find a route between supplied coordinates."""


@dataclass(frozen=True)
class RouteCandidate:
    coordinates: tuple[tuple[float, float], ...]
    distance_metres: float
    duration_seconds: float


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


def _post_json(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout) as error:
        raise OpenRouteServiceTimeout("OpenRouteService request timed out") from error
    except HTTPError as error:
        if error.code == 404:
            raise OpenRouteServiceNotFound(
                "OpenRouteService could not find a route"
            ) from error
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


class OpenRouteServiceDirections:
    def __init__(
        self,
        api_key: str,
        *,
        request_json: Callable[
            [str, dict[str, Any], dict[str, str], int], dict[str, Any]
        ] = _post_json,
    ) -> None:
        self._api_key = api_key
        self._request_json = request_json

    def alternatives(
        self,
        *,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> list[RouteCandidate]:
        return self._request_routes(
            {
                "coordinates": [list(origin), list(destination)],
                "alternative_routes": {
                    "target_count": 3,
                    "weight_factor": 1.4,
                    "share_factor": 0.6,
                },
            }
        )

    def route(
        self,
        *,
        origin: tuple[float, float],
        destination: tuple[float, float],
        avoid_polygons: dict[str, Any] | None = None,
        waypoints: tuple[tuple[float, float], ...] = (),
    ) -> RouteCandidate:
        body: dict[str, Any] = {
            "coordinates": [list(origin), *map(list, waypoints), list(destination)]
        }
        if avoid_polygons is not None:
            body["options"] = {"avoid_polygons": avoid_polygons}
        routes = self._request_routes(body)
        if not routes:
            raise OpenRouteServiceError("OpenRouteService returned no route")
        return routes[0]

    def _request_routes(self, body: dict[str, Any]) -> list[RouteCandidate]:
        headers = {
            "Accept": "application/geo+json",
            "Content-Type": "application/json",
            "Authorization": self._api_key,
        }
        try:
            payload = self._request_json(
                DIRECTION_URL,
                body,
                headers,
                REQUEST_TIMEOUT_SECONDS,
            )
        except OpenRouteServiceError:
            raise
        except (TimeoutError, socket.timeout) as error:
            raise OpenRouteServiceTimeout("OpenRouteService request timed out") from error
        except Exception as error:
            raise OpenRouteServiceError("OpenRouteService request failed") from error

        if payload.get("type") != "FeatureCollection" or not isinstance(
            payload.get("features"), list
        ):
            raise OpenRouteServiceError("OpenRouteService returned a malformed response")
        if not payload["features"]:
            raise OpenRouteServiceNotFound(
                "OpenRouteService could not find a route"
            )
        return [self._parse_route(feature) for feature in payload["features"]]

    @staticmethod
    def _parse_route(feature: Any) -> RouteCandidate:
        if not isinstance(feature, dict):
            raise OpenRouteServiceError("OpenRouteService returned a malformed route")
        geometry = feature.get("geometry")
        properties = feature.get("properties")
        if not isinstance(geometry, dict) or not isinstance(properties, dict):
            raise OpenRouteServiceError("OpenRouteService returned a malformed route")
        coordinates = geometry.get("coordinates")
        summary = properties.get("summary")
        if (
            geometry.get("type") != "LineString"
            or not isinstance(coordinates, list)
            or len(coordinates) < 2
            or not isinstance(summary, dict)
        ):
            raise OpenRouteServiceError("OpenRouteService returned a malformed route")
        distance = summary.get("distance")
        duration = summary.get("duration")
        if not _positive_number(distance) or not _positive_number(duration):
            raise OpenRouteServiceError("OpenRouteService returned a malformed route")

        parsed_coordinates = []
        for position in coordinates:
            if (
                not isinstance(position, list)
                or len(position) != 2
                or not all(_finite_number(value) for value in position)
            ):
                raise OpenRouteServiceError("OpenRouteService returned a malformed route")
            longitude, latitude = position
            if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                raise OpenRouteServiceError("OpenRouteService returned a malformed route")
            parsed_coordinates.append((float(longitude), float(latitude)))
        return RouteCandidate(
            coordinates=tuple(parsed_coordinates),
            distance_metres=float(distance),
            duration_seconds=float(duration),
        )


class OpenRouteServiceMatrix:
    def __init__(
        self,
        api_key: str,
        *,
        request_json: Callable[
            [str, dict[str, Any], dict[str, str], int], dict[str, Any]
        ] = _post_json,
    ) -> None:
        self._api_key = api_key
        self._request_json = request_json

    def distances(
        self,
        *,
        origin: tuple[float, float],
        destinations: tuple[tuple[float, float], ...],
    ) -> list[float | None]:
        if not destinations:
            return []

        return self.distances_for_sources(
            sources=(origin,),
            destinations=destinations,
        )[0]

    def distances_for_sources(
        self,
        *,
        sources: tuple[tuple[float, float], ...],
        destinations: tuple[tuple[float, float], ...],
    ) -> list[list[float | None]]:
        if not sources or not destinations:
            return []

        body = {
            "locations": [*map(list, sources), *map(list, destinations)],
            "sources": [str(index) for index in range(len(sources))],
            "destinations": [
                str(index)
                for index in range(len(sources), len(sources) + len(destinations))
            ],
            "metrics": ["distance"],
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self._api_key,
        }
        try:
            payload = self._request_json(
                MATRIX_URL,
                body,
                headers,
                REQUEST_TIMEOUT_SECONDS,
            )
        except OpenRouteServiceNotFound as error:
            raise OpenRouteServiceError(
                "OpenRouteService returned an HTTP error"
            ) from error
        except OpenRouteServiceError:
            raise
        except (TimeoutError, socket.timeout) as error:
            raise OpenRouteServiceTimeout(
                "OpenRouteService request timed out"
            ) from error
        except Exception as error:
            raise OpenRouteServiceError("OpenRouteService request failed") from error

        return self._parse_distance_matrix(
            payload,
            expected_source_count=len(sources),
            expected_destination_count=len(destinations),
        )

    @staticmethod
    def _parse_distance_matrix(
        payload: Any,
        *,
        expected_source_count: int,
        expected_destination_count: int,
    ) -> list[list[float | None]]:
        matrix = payload.get("distances") if isinstance(payload, dict) else None
        if (
            not isinstance(matrix, list)
            or len(matrix) != expected_source_count
            or any(
                not isinstance(row, list)
                or len(row) != expected_destination_count
                for row in matrix
            )
        ):
            raise OpenRouteServiceError(
                "OpenRouteService returned a malformed response"
            )

        distances = []
        for row in matrix:
            parsed_row: list[float | None] = []
            for value in row:
                if value is None:
                    parsed_row.append(None)
                elif _finite_number(value) and value >= 0:
                    parsed_row.append(float(value))
                else:
                    raise OpenRouteServiceError(
                        "OpenRouteService returned a malformed response"
                    )
            distances.append(parsed_row)
        return distances


def _finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _positive_number(value: Any) -> bool:
    return _finite_number(value) and value > 0
