from src.common.geojson import geometry_bounds, load_geojson_geometry, point_in_geometry
from src.functions.location_search.handler import BOUNDARY_PATH


POLYGON_WITH_HOLE = {
    "type": "Polygon",
    "coordinates": [
        [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
        [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],
    ],
}


def test_point_in_polygon_respects_outer_ring_holes_and_boundary():
    assert point_in_geometry(1, 1, POLYGON_WITH_HOLE) is True
    assert point_in_geometry(5, 5, POLYGON_WITH_HOLE) is False
    assert point_in_geometry(0, 5, POLYGON_WITH_HOLE) is True
    assert point_in_geometry(11, 5, POLYGON_WITH_HOLE) is False


def test_point_in_multipolygon_and_bounds():
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [POLYGON_WITH_HOLE["coordinates"]],
    }

    assert point_in_geometry(1, 1, geometry) is True
    assert geometry_bounds(geometry) == (0, 0, 10, 10)


def test_packaged_city_of_melbourne_boundary_accepts_cbd_and_rejects_clayton():
    geometry = load_geojson_geometry(BOUNDARY_PATH)

    assert point_in_geometry(144.9652, -37.8098, geometry) is True
    assert point_in_geometry(145.1340, -37.9110, geometry) is False
