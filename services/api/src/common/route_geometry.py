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
    segment_lengths = [
        math.hypot(*_relative_metres(start, end))
        for start, end in zip(route, route[1:])
    ]
    total_length = sum(segment_lengths)
    if total_length == 0:
        return route[:1] + route[-1:]

    points = [route[0]]
    segment_index = 0
    distance_before_segment = 0.0
    for sample_index in range(1, MAX_ROUTE_SAMPLE_POINTS - 1):
        target_distance = total_length * sample_index / (MAX_ROUTE_SAMPLE_POINTS - 1)
        while (
            segment_index < len(segment_lengths) - 1
            and distance_before_segment + segment_lengths[segment_index]
            < target_distance
        ):
            distance_before_segment += segment_lengths[segment_index]
            segment_index += 1
        segment_length = segment_lengths[segment_index]
        fraction = (
            0.0
            if segment_length == 0
            else (target_distance - distance_before_segment) / segment_length
        )
        points.append(
            _interpolate(route[segment_index], route[segment_index + 1], fraction)
        )
    points.append(route[-1])
    return tuple(points)


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
    unwrapped_longitudes = [longitudes[0]]
    for start, end in zip(longitudes, longitudes[1:]):
        unwrapped_longitudes.append(
            unwrapped_longitudes[-1] + _wrapped_longitude_delta(start, end)
        )
    latitude_buffer = math.degrees(ROUTE_BOUND_BUFFER_METRES / EARTH_RADIUS_METRES)
    maximum_latitude = max(abs(latitude) for latitude in latitudes)
    longitude_buffer = math.degrees(
        ROUTE_BOUND_BUFFER_METRES
        / (EARTH_RADIUS_METRES * max(math.cos(math.radians(maximum_latitude)), 1e-12))
    )
    west = min(unwrapped_longitudes) - longitude_buffer
    east = max(unwrapped_longitudes) + longitude_buffer
    if west < -180 or east > 180:
        west, east = -180, 180
    return BoundingBox(
        south=max(-90, min(latitudes) - latitude_buffer),
        west=west,
        north=min(90, max(latitudes) + latitude_buffer),
        east=east,
    )


def _point_to_segment_distance_metres(point, start, end) -> float:
    point_longitude, point_latitude = point
    start_longitude, start_latitude = start
    _, end_latitude = end
    longitude_scale = math.cos(
        math.radians((point_latitude + start_latitude + end_latitude) / 3)
    )
    start_longitude_delta = _wrapped_longitude_delta(
        point_longitude, start_longitude
    )
    end_longitude_delta = start_longitude_delta + _wrapped_longitude_delta(
        start_longitude, end[0]
    )
    start_x = (
        math.radians(start_longitude_delta)
        * EARTH_RADIUS_METRES
        * longitude_scale
    )
    end_x = math.radians(end_longitude_delta) * EARTH_RADIUS_METRES * longitude_scale
    start_y = math.radians(start_latitude - point_latitude) * EARTH_RADIUS_METRES
    end_y = math.radians(end_latitude - point_latitude) * EARTH_RADIUS_METRES
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
        math.radians(_wrapped_longitude_delta(origin_longitude, longitude))
        * EARTH_RADIUS_METRES
        * math.cos(mean_latitude)
    )
    north = math.radians(latitude - origin_latitude) * EARTH_RADIUS_METRES
    return east, north


def _interpolate(start, end, fraction) -> tuple[float, float]:
    longitude = start[0] + _wrapped_longitude_delta(start[0], end[0]) * fraction
    if longitude > 180:
        longitude -= 360
    elif longitude < -180:
        longitude += 360
    latitude = start[1] + (end[1] - start[1]) * fraction
    return longitude, latitude


def _wrapped_longitude_delta(start: float, end: float) -> float:
    return (end - start + 180) % 360 - 180


def _finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False
