"""Route candidate generation and sensory-score orchestration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
import math
from typing import Any, Protocol

from src.clients.open_route_service import OpenRouteServiceError, RouteCandidate
from src.common.geojson import geometry_bounds, point_in_geometry
from src.repositories.api import BoundingBox
from src.scoring.route import ScoringDataUnavailable, score_route


EARTH_RADIUS_METRES = 6_371_000
STALE_AFTER = timedelta(minutes=30)
MAX_ROUTES = 3
MIN_ROUTES = 2
MAX_AVOIDED_SENSORS = 20
AVOIDANCE_RADIUS_METRES = 60
AVOIDANCE_VERTICES = 12


class DirectionsLike(Protocol):
    def alternatives(self, *, origin, destination): ...

    def route(self, **kwargs): ...


class RouteDataLoaderLike(Protocol):
    def load(self, reference_time, bounds=None): ...


class RouteSearchDataUnavailable(RuntimeError):
    """Raised when at least two trustworthy route results cannot be produced."""


class RouteSearchService:
    def __init__(
        self,
        directions: DirectionsLike,
        data_loader: RouteDataLoaderLike,
        boundary_geometry: dict[str, Any],
        *,
        score_function: Callable = score_route,
    ) -> None:
        self._directions = directions
        self._data_loader = data_loader
        self._boundary = boundary_geometry
        self._score = score_function

    def search(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        *,
        reference_time: datetime,
    ) -> list[dict[str, Any]]:
        if reference_time.utcoffset() is None:
            raise ValueError("reference_time must be timezone-aware")

        candidates = self._deduplicate(
            self._directions.alternatives(origin=origin, destination=destination)
        )
        bounds = self._repository_bounds()
        sensors, refuges = self._data_loader.load(reference_time, bounds)
        scored = self._score_candidates(candidates, sensors, refuges)

        high_sensor_ids = {
            matched.location_id
            for _, result in scored
            for matched in result.matched_sensors
            if matched.high is True
        }
        if high_sensor_ids:
            by_id = {sensor.location_id: sensor for sensor in sensors}
            high_sensors = [
                by_id[location_id]
                for location_id in sorted(high_sensor_ids)
                if location_id in by_id
            ][:MAX_AVOIDED_SENSORS]
            if high_sensors:
                try:
                    avoidance = self._directions.route(
                        origin=origin,
                        destination=destination,
                        avoid_polygons=_avoidance_polygons(high_sensors),
                    )
                except OpenRouteServiceError:
                    pass
                else:
                    candidates = self._deduplicate([*candidates, avoidance])
                    scored = self._score_candidates(candidates, sensors, refuges)

        if len(scored) < MIN_ROUTES:
            for waypoint in _midpoint_waypoints(origin, destination):
                if not point_in_geometry(waypoint[0], waypoint[1], self._boundary):
                    continue
                try:
                    detour = self._directions.route(
                        origin=origin,
                        destination=destination,
                        waypoints=(waypoint,),
                    )
                except OpenRouteServiceError:
                    continue
                candidates = self._deduplicate([*candidates, detour])
                scored = self._score_candidates(candidates, sensors, refuges)
                if len(scored) >= MIN_ROUTES:
                    break

        if len(scored) < MIN_ROUTES:
            raise RouteSearchDataUnavailable(
                "At least two distinct scorable routes are required"
            )

        ordered = sorted(
            scored,
            key=lambda item: (item[1].score, item[0].duration_seconds),
        )[:MAX_ROUTES]
        return [
            self._response_route(
                candidate,
                score,
                sensors,
                reference_time,
                index=index,
            )
            for index, (candidate, score) in enumerate(ordered, start=1)
        ]

    def _score_candidates(self, candidates, sensors, refuges):
        scored = []
        for candidate in candidates:
            try:
                result = self._score(candidate.coordinates, sensors, refuges)
            except ScoringDataUnavailable:
                continue
            scored.append((candidate, result))
        return scored

    @staticmethod
    def _deduplicate(candidates: Sequence[RouteCandidate]) -> list[RouteCandidate]:
        unique = {}
        for candidate in candidates:
            signature = tuple(
                (round(longitude, 5), round(latitude, 5))
                for longitude, latitude in candidate.coordinates
            )
            unique.setdefault(signature, candidate)
        return list(unique.values())

    def _repository_bounds(self) -> BoundingBox:
        west, south, east, north = geometry_bounds(self._boundary)
        return BoundingBox(south=south, west=west, north=north, east=east)

    @staticmethod
    def _response_route(candidate, result, sensors, reference_time, *, index):
        sensors_by_id = {sensor.location_id: sensor for sensor in sensors}
        observed_times = [
            sensors_by_id[matched.location_id].latest_observed_at
            for matched in result.matched_sensors
            if matched.location_id in sensors_by_id
            and sensors_by_id[matched.location_id].latest_observed_at is not None
        ]
        observed_at = max(observed_times) if observed_times else None
        stale = observed_at is None or reference_time - observed_at > STALE_AFTER
        warning = result.warning
        if stale:
            stale_warning = "Pedestrian data may be stale."
            warning = f"{warning} {stale_warning}" if warning else stale_warning
        return {
            "id": f"route-{index}",
            "durationMinutes": math.ceil(candidate.duration_seconds / 60),
            "walkingDistanceKm": round(candidate.distance_metres / 1000, 2),
            "score": result.score,
            "indicator": result.indicator,
            "geometry": {
                "type": "LineString",
                "coordinates": [list(position) for position in candidate.coordinates],
            },
            "recommended": index == 1,
            "warning": warning,
            "explanation": result.explanation,
            "freshness": {
                "observedAt": observed_at.isoformat() if observed_at else None,
                "stale": stale,
                "fallbackUsed": result.fallback_used,
            },
        }


def _avoidance_polygons(sensors) -> dict[str, Any]:
    polygons = []
    for cluster in _overlapping_sensor_clusters(sensors):
        vertices = [
            vertex
            for sensor in cluster
            for vertex in _sensor_buffer_vertices(sensor)
        ]
        ring = [list(vertex) for vertex in _convex_hull(vertices)]
        ring.append(ring[0])
        polygons.append([ring])
    return {"type": "MultiPolygon", "coordinates": polygons}


def _overlapping_sensor_clusters(sensors):
    remaining = list(sensors)
    clusters = []
    while remaining:
        cluster = [remaining.pop(0)]
        changed = True
        while changed:
            changed = False
            for sensor in remaining[:]:
                if any(
                    _position_distance_metres(
                        (sensor.longitude, sensor.latitude),
                        (member.longitude, member.latitude),
                    )
                    <= AVOIDANCE_RADIUS_METRES * 2
                    for member in cluster
                ):
                    cluster.append(sensor)
                    remaining.remove(sensor)
                    changed = True
        clusters.append(cluster)
    return clusters


def _sensor_buffer_vertices(sensor):
    vertices = []
    for vertex in range(AVOIDANCE_VERTICES):
        angle = 2 * math.pi * vertex / AVOIDANCE_VERTICES
        vertices.append(
            _offset_position(
                (sensor.longitude, sensor.latitude),
                east_metres=AVOIDANCE_RADIUS_METRES * math.cos(angle),
                north_metres=AVOIDANCE_RADIUS_METRES * math.sin(angle),
            )
        )
    return vertices


def _convex_hull(points):
    ordered = sorted(set(points))
    if len(ordered) <= 1:
        return ordered

    def cross(origin, first, second):
        return (first[0] - origin[0]) * (second[1] - origin[1]) - (
            first[1] - origin[1]
        ) * (second[0] - origin[0])

    lower = []
    for point in ordered:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper = []
    for point in reversed(ordered):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)

    return lower[:-1] + upper[:-1]


def _midpoint_waypoints(origin, destination):
    origin_lon, origin_lat = origin
    destination_lon, destination_lat = destination
    mean_latitude = math.radians((origin_lat + destination_lat) / 2)
    east_metres = (
        math.radians(destination_lon - origin_lon)
        * EARTH_RADIUS_METRES
        * math.cos(mean_latitude)
    )
    north_metres = math.radians(destination_lat - origin_lat) * EARTH_RADIUS_METRES
    distance = math.hypot(east_metres, north_metres)
    if distance == 0:
        return ()
    offset = min(max(distance * 0.2, 100), 250)
    midpoint = (
        (origin_lon + destination_lon) / 2,
        (origin_lat + destination_lat) / 2,
    )
    perpendicular_east = -north_metres / distance * offset
    perpendicular_north = east_metres / distance * offset
    return (
        _offset_position(
            midpoint,
            east_metres=perpendicular_east,
            north_metres=perpendicular_north,
        ),
        _offset_position(
            midpoint,
            east_metres=-perpendicular_east,
            north_metres=-perpendicular_north,
        ),
    )


def _offset_position(position, *, east_metres, north_metres):
    longitude, latitude = position
    latitude_offset = math.degrees(north_metres / EARTH_RADIUS_METRES)
    longitude_offset = math.degrees(
        east_metres / (EARTH_RADIUS_METRES * math.cos(math.radians(latitude)))
    )
    return longitude + longitude_offset, latitude + latitude_offset


def _position_distance_metres(first, second):
    first_longitude, first_latitude = first
    second_longitude, second_latitude = second
    mean_latitude = math.radians((first_latitude + second_latitude) / 2)
    east_metres = (
        math.radians(second_longitude - first_longitude)
        * EARTH_RADIUS_METRES
        * math.cos(mean_latitude)
    )
    north_metres = (
        math.radians(second_latitude - first_latitude) * EARTH_RADIUS_METRES
    )
    return math.hypot(east_metres, north_metres)
