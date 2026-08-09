from __future__ import annotations

import pytest

from src.common.route_geometry import (
    point_to_route_distance_metres,
    route_bounds,
    sample_route_points,
    validate_route_geometry,
)


def test_validate_route_geometry_returns_longitude_latitude_positions():
    geometry = {
        "type": "LineString",
        "coordinates": [[144.9631, -37.8136], [144.9652, -37.8098]],
    }

    assert validate_route_geometry(geometry) == (
        (144.9631, -37.8136),
        (144.9652, -37.8098),
    )


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Polygon", "coordinates": []},
        {"type": "LineString", "coordinates": [[144.96, -37.81]]},
        {"type": "LineString", "coordinates": [[144.96, -37.81, 1], [144.97, -37.80]]},
        {"type": "LineString", "coordinates": [[181, -37.81], [144.97, -37.80]]},
        {"type": "LineString", "coordinates": [[144.96, float("nan")], [144.97, -37.80]]},
        {"type": "LineString", "coordinates": [[10**400, -37.81], [144.97, -37.80]]},
    ],
)
def test_validate_route_geometry_rejects_malformed_linestrings(geometry):
    with pytest.raises(ValueError, match="route geometry"):
        validate_route_geometry(geometry)


def test_sample_route_points_interpolates_fifty_sources_along_a_sparse_segment():
    route = ((0.0, 0.0), (49.0, 0.0))

    points = sample_route_points(route)

    assert len(points) == 50
    assert [point[0] for point in points] == pytest.approx(range(50))
    assert all(point[1] == 0.0 for point in points)


def test_sample_route_points_uses_distance_not_vertex_density():
    route = ((0.0, 0.0), (0.01, 0.0), (0.02, 0.0), (10.0, 0.0))

    points = sample_route_points(route)

    assert len(points) == 50
    assert points[0] == (0.0, 0.0)
    assert points[1] == pytest.approx((0.2040816327, 0.0))
    assert points[24] == pytest.approx((4.8979591837, 0.0))
    assert points[-1] == (10.0, 0.0)


def test_point_to_route_distance_uses_the_nearest_line_segment():
    route = ((144.9600, -37.8100), (144.9600, -37.8000))

    distance = point_to_route_distance_metres((144.9610, -37.8050), route)

    assert distance == pytest.approx(88, abs=1)


def test_route_bounds_adds_one_kilometre_buffer_to_every_side():
    bounds = route_bounds(((0.0, 0.0), (0.1, 0.0)))

    assert bounds.south == pytest.approx(-0.00899, abs=0.00001)
    assert bounds.west == pytest.approx(-0.00899, abs=0.00001)
    assert bounds.north == pytest.approx(0.00899, abs=0.00001)
    assert bounds.east == pytest.approx(0.10899, abs=0.00001)


def test_route_bounds_uses_world_longitudes_when_buffer_crosses_dateline():
    bounds = route_bounds(((179.9990, 0.0), (179.9995, 0.0)))

    assert bounds.west == -180
    assert bounds.east == 180


def test_route_bounds_uses_world_longitudes_for_a_dateline_crossing_route():
    bounds = route_bounds(((170.0, 0.0), (-170.0, 0.0)))

    assert bounds.west == -180
    assert bounds.east == 180


def test_point_to_route_distance_follows_a_segment_across_the_dateline():
    route = ((179.9990, 0.0), (-179.9990, 0.0))

    distance = point_to_route_distance_metres((180.0, 0.0), route)

    assert distance == pytest.approx(0, abs=0.01)


def test_point_to_route_distance_does_not_cross_the_antipodal_non_corridor():
    route = ((179.0, 0.0), (-179.0, 0.0))

    distance = point_to_route_distance_metres((0.0, 0.0), route)

    assert distance > 19_000_000
