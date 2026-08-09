"""Validation and calculations for GeoJSON journey routes."""

from __future__ import annotations

import math
from typing import Any

from src.repositories.api import BoundingBox


MAX_ROUTE_COORDINATES = 2_000
MAX_ROUTE_SAMPLE_POINTS = 50
EARTH_RADIUS_METRES = 6_371_000
ROUTE_BOUND_BUFFER_METRES = 1_000


def validate_route_geometry(geometry: Any) -> tuple[tuple[float, float], ...]:
    """Return valid LineString positions as longitude/latitude pairs."""
    if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
        raise ValueError("route geometry must be a GeoJSON LineString")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or not 2 <= len(coordinates) <= MAX_ROUTE_COORDINATES:
        raise ValueError("route geometry must contain 2 to 2,000 coordinates")

    positions = []
    for position in coordinates:
        if (
            not isinstance(position, list)
            or len(position) != 2
            or not all(_finite_number(value) for value in position)
        ):
            raise ValueError("route geometry contains an invalid coordinate")
        longitude, latitude = position
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError("route geometry contains an invalid coordinate")
        positions.append((float(longitude), float(latitude)))
    return tuple(positions)


def sample_route_points(
    route: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...]:
    """Return evenly spaced route points, retaining both endpoints."""
    if len(route) <= MAX_ROUTE_SAMPLE_POINTS:
        return route
    last_index = len(route) - 1
    return tuple(
        route[round(index * last_index / (MAX_ROUTE_SAMPLE_POINTS - 1))]
        for index in range(MAX_ROUTE_SAMPLE_POINTS)
    )


def point_to_route_distance_metres(
    point: tuple[float, float],
    route: tuple[tuple[float, float], ...],
) -> float:
    """Return the shortest local planar distance from a point to a route."""
    return min(
        _point_to_segment_distance_metres(point, start, end)
        for start, end in zip(route, route[1:])
    )


def route_bounds(route: tuple[tuple[float, float], ...]) -> BoundingBox:
    """Return a bounding box around a route with a one-kilometre buffer."""
    longitudes, latitudes = zip(*route, strict=True)
    latitude_buffer = math.degrees(ROUTE_BOUND_BUFFER_METRES / EARTH_RADIUS_METRES)
    maximum_latitude = max(abs(latitude) for latitude in latitudes)
    longitude_buffer = math.degrees(
        ROUTE_BOUND_BUFFER_METRES
        / (EARTH_RADIUS_METRES * max(math.cos(math.radians(maximum_latitude)), 1e-12))
    )
    return BoundingBox(
        south=max(-90, min(latitudes) - latitude_buffer),
        west=max(-180, min(longitudes) - longitude_buffer),
        north=min(90, max(latitudes) + latitude_buffer),
        east=min(180, max(longitudes) + longitude_buffer),
    )


def _point_to_segment_distance_metres(point, start, end) -> float:
    start_x, start_y = _relative_metres(point, start)
    end_x, end_y = _relative_metres(point, end)
    segment_x = end_x - start_x
    segment_y = end_y - start_y
    segment_squared = segment_x**2 + segment_y**2
    if segment_squared == 0:
        return math.hypot(start_x, start_y)
    projection = max(
        0.0,
        min(1.0, -(start_x * segment_x + start_y * segment_y) / segment_squared),
    )
    return math.hypot(
        start_x + projection * segment_x,
        start_y + projection * segment_y,
    )


def _relative_metres(origin, position) -> tuple[float, float]:
    origin_longitude, origin_latitude = origin
    longitude, latitude = position
    mean_latitude = math.radians((origin_latitude + latitude) / 2)
    east = (
        math.radians(longitude - origin_longitude)
        * EARTH_RADIUS_METRES
        * math.cos(mean_latitude)
    )
    north = math.radians(latitude - origin_latitude) * EARTH_RADIUS_METRES
    return east, north


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
