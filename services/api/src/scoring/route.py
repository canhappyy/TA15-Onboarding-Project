"""Pure route-level sensory scoring for Melbourne walking routes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Protocol


EARTH_RADIUS_METRES = 6_371_000
DIRECT_MATCH_METRES = 100
FALLBACK_MATCH_METRES = 500
FALLBACK_SENSOR_LIMIT = 3
REFUGE_RADIUS_METRES = 250
REFUGE_TARGET = 3
HIGH_SCORE_THRESHOLD = 50
EXPLANATION = (
    "Calculated using pedestrian crowd information and nearby refuge "
    "availability."
)

RouteCoordinate = tuple[float, float]


class SensorLike(Protocol):
    location_id: int
    name: str
    latitude: float
    longitude: float
    live_60_minute_total: int | None
    historical_hourly_mean: float | None
    historical_hourly_p75: float | None


class RefugeLike(Protocol):
    latitude: float
    longitude: float


class ScoringDataUnavailable(RuntimeError):
    """Raised when a route has no usable pedestrian observations."""


@dataclass(frozen=True)
class MatchedSensor:
    location_id: int
    name: str
    distance_metres: float
    reading_used: float | None
    threshold: float | None
    high: bool | None
    fallback_used: bool


@dataclass(frozen=True)
class RouteScore:
    score: int
    indicator: str
    fallback_used: bool
    matched_sensors: tuple[MatchedSensor, ...]
    refuges_within_250m: int
    warning: str | None
    explanation: str = EXPLANATION


def score_route(
    route_coordinates: Sequence[RouteCoordinate],
    sensors: Sequence[SensorLike],
    refuges: Sequence[RefugeLike],
) -> RouteScore:
    """Score one GeoJSON-order route without database or network access."""
    route = _validate_route(route_coordinates)
    matched = _match_sensors(route, sensors)
    evaluated = tuple(
        _evaluate_sensor(sensor, distance) for distance, sensor in matched
    )
    scorable = [sensor for sensor in evaluated if sensor.high is not None]
    if not scorable:
        raise ScoringDataUnavailable(
            "No matched sensor has a usable reading and historical baseline"
        )

    high_count = sum(sensor.high is True for sensor in scorable)
    high_sensor_ratio = Decimal(high_count) / Decimal(len(scorable))
    refuge_count = sum(
        distance_to_route_metres(
            latitude=refuge.latitude,
            longitude=refuge.longitude,
            route_coordinates=route,
        )
        <= REFUGE_RADIUS_METRES
        for refuge in refuges
    )
    refuge_coverage = min(
        Decimal(refuge_count) / Decimal(REFUGE_TARGET), Decimal(1)
    )
    raw_score = Decimal(100) * (
        Decimal("0.85") * high_sensor_ratio
        + Decimal("0.15") * (Decimal(1) - refuge_coverage)
    )
    score = int(raw_score.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    fallback_used = any(sensor.fallback_used for sensor in scorable)
    warning = _warning(
        high_sensor_ratio=float(high_sensor_ratio),
        fallback_used=fallback_used,
        unavailable_count=len(evaluated) - len(scorable),
    )
    return RouteScore(
        score=score,
        indicator=indicator_for_score(score),
        fallback_used=fallback_used,
        matched_sensors=evaluated,
        refuges_within_250m=refuge_count,
        warning=warning,
    )


def indicator_for_score(score: int) -> str:
    return "HIGH" if score >= HIGH_SCORE_THRESHOLD else "LOW"


def distance_to_route_metres(
    *,
    latitude: float,
    longitude: float,
    route_coordinates: Sequence[RouteCoordinate],
) -> float:
    """Return local equirectangular point-to-polyline distance in metres."""
    route = _validate_route(route_coordinates)
    _validate_position(longitude, latitude, label="point")
    projected = [
        _project_relative(
            longitude=route_longitude,
            latitude=route_latitude,
            origin_longitude=longitude,
            origin_latitude=latitude,
        )
        for route_longitude, route_latitude in route
    ]
    return min(
        _distance_from_origin_to_segment(start, end)
        for start, end in zip(projected, projected[1:])
    )


def _match_sensors(
    route: tuple[RouteCoordinate, ...],
    sensors: Sequence[SensorLike],
) -> list[tuple[float, SensorLike]]:
    distances = sorted(
        (
            (
                distance_to_route_metres(
                    latitude=sensor.latitude,
                    longitude=sensor.longitude,
                    route_coordinates=route,
                ),
                sensor,
            )
            for sensor in sensors
        ),
        key=lambda item: (item[0], item[1].location_id),
    )
    direct = [item for item in distances if item[0] <= DIRECT_MATCH_METRES]
    if direct:
        return direct
    fallback = [item for item in distances if item[0] <= FALLBACK_MATCH_METRES]
    if not fallback:
        raise ScoringDataUnavailable("No nearby sensors are available for this route")
    return fallback[:FALLBACK_SENSOR_LIMIT]


def _evaluate_sensor(
    sensor: SensorLike,
    distance_metres: float,
) -> MatchedSensor:
    threshold = sensor.historical_hourly_p75
    fallback_used = sensor.live_60_minute_total is None
    reading = (
        sensor.historical_hourly_mean
        if fallback_used
        else float(sensor.live_60_minute_total)
    )
    high = (
        reading >= threshold
        if reading is not None and threshold is not None
        else None
    )
    return MatchedSensor(
        location_id=sensor.location_id,
        name=sensor.name,
        distance_metres=distance_metres,
        reading_used=reading,
        threshold=threshold,
        high=high,
        fallback_used=fallback_used and reading is not None,
    )


def _warning(
    *,
    high_sensor_ratio: float,
    fallback_used: bool,
    unavailable_count: int,
) -> str | None:
    if high_sensor_ratio > 0:
        return "High pedestrian density is expected on this route."
    if fallback_used:
        return (
            "Live pedestrian data is unavailable; historical averages were used."
        )
    if unavailable_count:
        return "Some pedestrian sensor data is unavailable."
    return None


def _validate_route(
    route_coordinates: Sequence[RouteCoordinate],
) -> tuple[RouteCoordinate, ...]:
    if len(route_coordinates) < 2:
        raise ValueError("route must contain at least two coordinates")
    route = []
    for position in route_coordinates:
        if not isinstance(position, (tuple, list)) or len(position) != 2:
            raise ValueError("route coordinates must be longitude/latitude pairs")
        longitude, latitude = position
        _validate_position(longitude, latitude, label="route")
        route.append((float(longitude), float(latitude)))
    return tuple(route)


def _validate_position(longitude: float, latitude: float, *, label: str) -> None:
    if not isinstance(longitude, (int, float)) or not isinstance(
        latitude, (int, float)
    ):
        raise ValueError(f"{label} coordinates must be numeric")
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        raise ValueError(f"{label} coordinates must be finite")
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError(f"{label} coordinates are outside valid ranges")


def _project_relative(
    *,
    longitude: float,
    latitude: float,
    origin_longitude: float,
    origin_latitude: float,
) -> tuple[float, float]:
    mean_latitude = math.radians((latitude + origin_latitude) / 2)
    x = (
        math.radians(longitude - origin_longitude)
        * EARTH_RADIUS_METRES
        * math.cos(mean_latitude)
    )
    y = math.radians(latitude - origin_latitude) * EARTH_RADIUS_METRES
    return x, y


def _distance_from_origin_to_segment(
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    segment_x = end[0] - start[0]
    segment_y = end[1] - start[1]
    length_squared = segment_x * segment_x + segment_y * segment_y
    if length_squared == 0:
        return math.hypot(*start)
    projection = -(start[0] * segment_x + start[1] * segment_y) / length_squared
    position = min(max(projection, 0), 1)
    closest_x = start[0] + position * segment_x
    closest_y = start[1] + position * segment_y
    return math.hypot(closest_x, closest_y)
