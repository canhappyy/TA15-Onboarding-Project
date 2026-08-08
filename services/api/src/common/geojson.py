from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_geojson_geometry(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as boundary_file:
        document = json.load(boundary_file)

    if document.get("type") == "FeatureCollection":
        features = document.get("features")
        if not isinstance(features, list) or len(features) != 1:
            raise ValueError("Boundary GeoJSON must contain exactly one feature")
        document = features[0]

    if document.get("type") == "Feature":
        document = document.get("geometry")

    if not isinstance(document, dict) or document.get("type") not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Boundary GeoJSON must contain a Polygon or MultiPolygon")
    return document


def geometry_bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    positions = list(_positions(geometry))
    if not positions:
        raise ValueError("Boundary geometry contains no coordinates")

    longitudes = [position[0] for position in positions]
    latitudes = [position[1] for position in positions]
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


def point_in_geometry(longitude: float, latitude: float, geometry: dict[str, Any]) -> bool:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        polygons = [coordinates]
    elif geometry_type == "MultiPolygon":
        polygons = coordinates
    else:
        raise ValueError("Unsupported boundary geometry type")

    if not isinstance(polygons, list):
        raise ValueError("Boundary geometry has invalid coordinates")
    return any(_point_in_polygon(longitude, latitude, polygon) for polygon in polygons)


def _positions(geometry: dict[str, Any]):
    coordinates = geometry.get("coordinates")
    geometry_type = geometry.get("type")
    polygons = [coordinates] if geometry_type == "Polygon" else coordinates
    if not isinstance(polygons, list):
        return
    for polygon in polygons:
        if not isinstance(polygon, list):
            continue
        for ring in polygon:
            if not isinstance(ring, list):
                continue
            for position in ring:
                if (
                    isinstance(position, list)
                    and len(position) >= 2
                    and isinstance(position[0], (int, float))
                    and isinstance(position[1], (int, float))
                ):
                    yield position[0], position[1]


def _point_in_polygon(longitude: float, latitude: float, polygon: Any) -> bool:
    if not isinstance(polygon, list) or not polygon:
        return False
    if not _point_in_ring(longitude, latitude, polygon[0]):
        return False
    return not any(_point_in_ring(longitude, latitude, hole) for hole in polygon[1:])


def _point_in_ring(longitude: float, latitude: float, ring: Any) -> bool:
    if not isinstance(ring, list) or len(ring) < 4:
        return False

    inside = False
    previous = ring[-1]
    for current in ring:
        if _point_on_segment(longitude, latitude, previous, current):
            return True

        current_lon, current_lat = current[:2]
        previous_lon, previous_lat = previous[:2]
        crosses = (current_lat > latitude) != (previous_lat > latitude)
        if crosses:
            intersection = (
                (previous_lon - current_lon)
                * (latitude - current_lat)
                / (previous_lat - current_lat)
                + current_lon
            )
            if longitude < intersection:
                inside = not inside
        previous = current
    return inside


def _point_on_segment(longitude: float, latitude: float, start: Any, end: Any) -> bool:
    start_lon, start_lat = start[:2]
    end_lon, end_lat = end[:2]
    cross_product = (latitude - start_lat) * (end_lon - start_lon) - (
        longitude - start_lon
    ) * (end_lat - start_lat)
    if abs(cross_product) > 1e-10:
        return False
    return (
        min(start_lon, end_lon) - 1e-10 <= longitude <= max(start_lon, end_lon) + 1e-10
        and min(start_lat, end_lat) - 1e-10 <= latitude <= max(start_lat, end_lat) + 1e-10
    )
