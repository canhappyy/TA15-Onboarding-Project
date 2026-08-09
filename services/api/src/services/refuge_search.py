"""Walking-distance refuge search."""

from __future__ import annotations

import math
from collections.abc import Collection, Sequence
from typing import Any, Protocol, cast
from urllib.parse import urlencode

from src.common.route_geometry import (
    point_to_route_distance_metres,
    route_bounds,
    sample_route_points,
)
from src.repositories.api import BoundingBox, RefugeRecord


EARTH_RADIUS_METRES = 6_371_000
SEARCH_RADIUS_METRES = 1_000
MAX_MATRIX_CANDIDATES = 50
MAX_RESULTS = 20
REFUGE_SOURCE = "City of Melbourne Open Data"


class MatrixLike(Protocol):
    def distances(
        self,
        *,
        origin: tuple[float, float],
        destinations: tuple[tuple[float, float], ...],
    ) -> list[float | None]: ...


class RefugeDataLoaderLike(Protocol):
    def load(
        self,
        origin: tuple[float, float],
        category: str | None = None,
    ) -> list[RefugeRecord]: ...


class RouteMatrixLike(Protocol):
    def distances_for_sources(
        self,
        *,
        sources: tuple[tuple[float, float], ...],
        destinations: tuple[tuple[float, float], ...],
    ) -> list[list[float | None]]: ...


class RouteRefugeDataLoaderLike(Protocol):
    def load_for_route(
        self,
        *,
        bounds: BoundingBox,
        categories: Collection[str] | None = None,
    ) -> list[RefugeRecord]: ...


class RefugeSearchDataUnavailable(RuntimeError):
    """Raised when read-only refuge data cannot be loaded."""


class RefugeSearchService:
    def __init__(self, matrix: MatrixLike, data_loader: RefugeDataLoaderLike) -> None:
        self._matrix = matrix
        self._data_loader = data_loader

    def search(
        self,
        origin: tuple[float, float],
        *,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        candidates = self._nearest_candidates(
            origin,
            self._data_loader.load(origin, category),
        )
        if not candidates:
            return []

        destinations = tuple(
            (refuge.longitude, refuge.latitude) for refuge in candidates
        )
        walking_distances = self._matrix.distances(
            origin=origin,
            destinations=destinations,
        )
        reachable = [
            (refuge, distance)
            for refuge, distance in zip(candidates, walking_distances, strict=True)
            if distance is not None and distance <= SEARCH_RADIUS_METRES
        ]
        return [
            self._response_refuge(refuge, distance)
            for refuge, distance in sorted(
                reachable,
                key=lambda item: (item[1], item[0].name, item[0].landmark_id),
            )[:MAX_RESULTS]
        ]

    def search_route(
        self,
        route: tuple[tuple[float, float], ...],
        *,
        categories: Collection[str] | None = None,
    ) -> list[dict[str, Any]]:
        data_loader = cast(RouteRefugeDataLoaderLike, self._data_loader)
        candidates = self._route_candidates(
            route,
            data_loader.load_for_route(
                bounds=route_bounds(route),
                categories=categories,
            ),
        )
        if not candidates:
            return []

        route_points = sample_route_points(route)
        matrix = cast(RouteMatrixLike, self._matrix)
        walking_distances = matrix.distances_for_sources(
            sources=route_points,
            destinations=tuple(
                (refuge.longitude, refuge.latitude) for refuge in candidates
            ),
        )
        reachable = [
            (refuge, minimum_distance)
            for refuge, distances in zip(
                candidates,
                zip(*walking_distances, strict=True),
                strict=True,
            )
            if (minimum_distance := min(
                (distance for distance in distances if distance is not None),
                default=None,
            )) is not None
            and minimum_distance <= SEARCH_RADIUS_METRES
        ]
        return [
            self._response_refuge(refuge, distance)
            for refuge, distance in sorted(
                reachable,
                key=lambda item: (item[1], item[0].name, item[0].landmark_id),
            )[:MAX_RESULTS]
        ]

    @staticmethod
    def _nearest_candidates(
        origin: tuple[float, float],
        refuges: Sequence[RefugeRecord],
    ) -> list[RefugeRecord]:
        nearby = [
            (refuge, _distance_metres(origin, (refuge.longitude, refuge.latitude)))
            for refuge in refuges
        ]
        return [
            refuge
            for refuge, _ in sorted(
                (
                    item
                    for item in nearby
                    if item[1] <= SEARCH_RADIUS_METRES
                ),
                key=lambda item: (item[1], item[0].name, item[0].landmark_id),
            )[:MAX_MATRIX_CANDIDATES]
        ]

    @staticmethod
    def _route_candidates(
        route: tuple[tuple[float, float], ...],
        refuges: Sequence[RefugeRecord],
    ) -> list[RefugeRecord]:
        nearby = [
            (
                refuge,
                point_to_route_distance_metres(
                    (refuge.longitude, refuge.latitude),
                    route,
                ),
            )
            for refuge in refuges
        ]
        return [
            refuge
            for refuge, _ in sorted(
                (item for item in nearby if item[1] <= SEARCH_RADIUS_METRES),
                key=lambda item: (item[1], item[0].name, item[0].landmark_id),
            )[:MAX_MATRIX_CANDIDATES]
        ]

    @staticmethod
    def _response_refuge(refuge: RefugeRecord, walking_distance_metres: float):
        destination = f"{refuge.latitude},{refuge.longitude}"
        navigation_url = "https://www.google.com/maps/dir/?" + urlencode(
            {
                "api": 1,
                "destination": destination,
                "travelmode": "walking",
            }
        )
        return {
            "id": f"landmark-{refuge.landmark_id}",
            "name": refuge.name,
            "category": refuge.category,
            "coordinates": {
                "latitude": refuge.latitude,
                "longitude": refuge.longitude,
            },
            "walkingDistanceKm": round(walking_distance_metres / 1_000, 2),
            "metadata": {"source": REFUGE_SOURCE},
            "navigationUrl": navigation_url,
        }


def _distance_metres(
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    start_lon, start_lat = start
    end_lon, end_lat = end
    latitude_delta = math.radians(end_lat - start_lat)
    longitude_delta = math.radians(end_lon - start_lon)
    start_latitude = math.radians(start_lat)
    end_latitude = math.radians(end_lat)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(start_latitude)
        * math.cos(end_latitude)
        * math.sin(longitude_delta / 2) ** 2
    )
    return EARTH_RADIUS_METRES * 2 * math.atan2(
        math.sqrt(haversine),
        math.sqrt(1 - haversine),
    )
