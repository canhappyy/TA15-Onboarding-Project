import pytest

from src.clients.open_route_service import (
    DIRECTION_URL,
    MATRIX_URL,
    OpenRouteServiceError,
    OpenRouteServiceDirections,
    OpenRouteServiceGeocoder,
    OpenRouteServiceMatrix,
    OpenRouteServiceNotFound,
    OpenRouteServiceTimeout,
    RouteCandidate,
)


MELBOURNE_BOUNDS = (144.89, -37.86, 145.00, -37.77)


def test_geocoder_builds_bounded_request_and_parses_features():
    captured = {}

    def request_json(url, params, timeout):
        captured.update(url=url, params=params, timeout=timeout)
        return {
            "features": [
                {
                    "geometry": {"type": "Point", "coordinates": [144.9652, -37.8098]},
                    "properties": {
                        "gid": "venue.123",
                        "label": "State Library Victoria, Melbourne VIC",
                    },
                }
            ]
        }

    results = OpenRouteServiceGeocoder(
        "secret-key",
        request_json=request_json,
    ).search("State Library", bounds=MELBOURNE_BOUNDS, limit=10)

    assert captured["url"] == "https://api.heigit.org/pelias/v1/search"
    assert captured["timeout"] == 5
    assert captured["params"] == {
        "api_key": "secret-key",
        "text": "State Library",
        "size": 10,
        "boundary.rect.min_lon": 144.89,
        "boundary.rect.min_lat": -37.86,
        "boundary.rect.max_lon": 145.0,
        "boundary.rect.max_lat": -37.77,
    }
    assert results == [
        {
            "id": "venue.123",
            "label": "State Library Victoria, Melbourne VIC",
            "coordinates": {"latitude": -37.8098, "longitude": 144.9652},
        }
    ]


def test_geocoder_maps_timeout():
    def request_json(url, params, timeout):
        raise TimeoutError("timed out")

    with pytest.raises(OpenRouteServiceTimeout):
        OpenRouteServiceGeocoder("secret-key", request_json=request_json).search(
            "Library",
            bounds=MELBOURNE_BOUNDS,
        )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"features": "not-a-list"},
        {
            "features": [
                {
                    "geometry": {"type": "Point", "coordinates": [144.96]},
                    "properties": {"gid": "bad", "label": "Bad feature"},
                }
            ]
        },
    ],
)
def test_geocoder_rejects_malformed_responses(payload):
    with pytest.raises(OpenRouteServiceError, match="malformed"):
        OpenRouteServiceGeocoder(
            "secret-key",
            request_json=lambda url, params, timeout: payload,
        ).search("Library", bounds=MELBOURNE_BOUNDS)


def route_feature(*, distance=1300, duration=1080, coordinates=None):
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
            or [[144.9671, -37.8179], [144.9652, -37.8098]],
        },
        "properties": {
            "summary": {"distance": distance, "duration": duration},
        },
    }


def test_directions_requests_three_walking_alternatives_and_parses_geojson():
    captured = {}

    def request_json(url, body, headers, timeout):
        captured.update(url=url, body=body, headers=headers, timeout=timeout)
        return {
            "type": "FeatureCollection",
            "features": [route_feature(), route_feature(distance=1450, duration=1200)],
        }

    routes = OpenRouteServiceDirections(
        "secret-key",
        request_json=request_json,
    ).alternatives(
        origin=(144.9671, -37.8179),
        destination=(144.9652, -37.8098),
    )

    assert captured == {
        "url": DIRECTION_URL,
        "body": {
            "coordinates": [
                [144.9671, -37.8179],
                [144.9652, -37.8098],
            ],
            "alternative_routes": {
                "target_count": 3,
                "weight_factor": 1.4,
                "share_factor": 0.6,
            },
        },
        "headers": {
            "Accept": "application/geo+json",
            "Content-Type": "application/json",
            "Authorization": "secret-key",
        },
        "timeout": 5,
    }
    assert routes == [
        RouteCandidate(
            coordinates=((144.9671, -37.8179), (144.9652, -37.8098)),
            distance_metres=1300.0,
            duration_seconds=1080.0,
        ),
        RouteCandidate(
            coordinates=((144.9671, -37.8179), (144.9652, -37.8098)),
            distance_metres=1450.0,
            duration_seconds=1200.0,
        ),
    ]


def test_directions_sends_avoidance_polygon_and_waypoint_requests():
    bodies = []

    def request_json(url, body, headers, timeout):
        bodies.append(body)
        return {"type": "FeatureCollection", "features": [route_feature()]}

    client = OpenRouteServiceDirections("secret-key", request_json=request_json)
    polygon = {
        "type": "Polygon",
        "coordinates": [[[144.96, -37.81], [144.961, -37.81], [144.96, -37.81]]],
    }
    client.route(
        origin=(144.9671, -37.8179),
        destination=(144.9652, -37.8098),
        avoid_polygons=polygon,
    )
    client.route(
        origin=(144.9671, -37.8179),
        destination=(144.9652, -37.8098),
        waypoints=((144.97, -37.813),),
    )

    assert bodies == [
        {
            "coordinates": [[144.9671, -37.8179], [144.9652, -37.8098]],
            "options": {"avoid_polygons": polygon},
        },
        {
            "coordinates": [
                [144.9671, -37.8179],
                [144.97, -37.813],
                [144.9652, -37.8098],
            ]
        },
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"type": "FeatureCollection", "features": "bad"},
        {"type": "FeatureCollection", "features": [route_feature(distance=0)]},
        {
            "type": "FeatureCollection",
            "features": [route_feature(coordinates=[[144.96, -37.81]])],
        },
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": []},
                    "properties": {},
                }
            ],
        },
    ],
)
def test_directions_rejects_malformed_responses(payload):
    with pytest.raises(OpenRouteServiceError, match="malformed"):
        OpenRouteServiceDirections(
            "secret-key",
            request_json=lambda url, body, headers, timeout: payload,
        ).alternatives(
            origin=(144.9671, -37.8179),
            destination=(144.9652, -37.8098),
        )


def test_directions_maps_timeout_without_exposing_request_data():
    def request_json(url, body, headers, timeout):
        raise TimeoutError("timed out")

    with pytest.raises(OpenRouteServiceTimeout, match="timed out"):
        OpenRouteServiceDirections(
            "secret-key",
            request_json=request_json,
        ).alternatives(
            origin=(144.9671, -37.8179),
            destination=(144.9652, -37.8098),
        )


def test_directions_reports_no_route_when_feature_collection_is_empty():
    with pytest.raises(OpenRouteServiceNotFound):
        OpenRouteServiceDirections(
            "secret-key",
            request_json=lambda url, body, headers, timeout: {
                "type": "FeatureCollection",
                "features": [],
            },
        ).alternatives(
            origin=(144.9671, -37.8179),
            destination=(144.9652, -37.8098),
        )


def test_matrix_sends_one_foot_walking_request_and_returns_distances():
    captured = {}

    def request_json(url, body, headers, timeout):
        captured.update(url=url, body=body, headers=headers, timeout=timeout)
        return {"distances": [[218.4, None, 904.7]]}

    distances = OpenRouteServiceMatrix(
        "secret-key",
        request_json=request_json,
    ).distances(
        origin=(144.9631, -37.8136),
        destinations=(
            (144.9652, -37.8098),
            (144.9720, -37.8150),
            (144.9580, -37.8170),
        ),
    )

    assert captured == {
        "url": MATRIX_URL,
        "body": {
            "locations": [
                [144.9631, -37.8136],
                [144.9652, -37.8098],
                [144.972, -37.815],
                [144.958, -37.817],
            ],
            "sources": ["0"],
            "destinations": ["1", "2", "3"],
            "metrics": ["distance"],
        },
        "headers": {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "secret-key",
        },
        "timeout": 5,
    }
    assert distances == [218.4, None, 904.7]


def test_matrix_sends_one_request_for_many_sources_and_destinations():
    captured = {}

    def request_json(url, body, headers, timeout):
        captured.update(url=url, body=body, headers=headers, timeout=timeout)
        return {"distances": [[218.4, None], [904.7, 150.0]]}

    distances = OpenRouteServiceMatrix(
        "secret-key",
        request_json=request_json,
    ).distances_for_sources(
        sources=((144.9631, -37.8136), (144.9720, -37.8150)),
        destinations=((144.9652, -37.8098), (144.9580, -37.8170)),
    )

    assert captured == {
        "url": MATRIX_URL,
        "body": {
            "locations": [
                [144.9631, -37.8136],
                [144.972, -37.815],
                [144.9652, -37.8098],
                [144.958, -37.817],
            ],
            "sources": ["0", "1"],
            "destinations": ["2", "3"],
            "metrics": ["distance"],
        },
        "headers": {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "secret-key",
        },
        "timeout": 5,
    }
    assert distances == [[218.4, None], [904.7, 150.0]]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"distances": []},
        {"distances": "bad"},
        {"distances": [[218.4]]},
        {"distances": [[218.4, "bad", 904.7]]},
        {"distances": [[218.4, float("inf"), 904.7]]},
    ],
)
def test_matrix_rejects_malformed_distance_envelopes(payload):
    with pytest.raises(OpenRouteServiceError, match="malformed"):
        OpenRouteServiceMatrix(
            "secret-key",
            request_json=lambda url, body, headers, timeout: payload,
        ).distances(
            origin=(144.9631, -37.8136),
            destinations=(
                (144.9652, -37.8098),
                (144.9720, -37.8150),
                (144.9580, -37.8170),
            ),
        )


def test_matrix_maps_timeout_without_exposing_coordinates():
    def request_json(url, body, headers, timeout):
        raise TimeoutError("timed out")

    with pytest.raises(OpenRouteServiceTimeout, match="timed out"):
        OpenRouteServiceMatrix("secret-key", request_json=request_json).distances(
            origin=(144.9631, -37.8136),
            destinations=((144.9652, -37.8098),),
        )


def test_matrix_maps_request_failure_to_ors_error():
    def request_json(url, body, headers, timeout):
        raise RuntimeError("upstream unavailable")

    with pytest.raises(OpenRouteServiceError, match="request failed"):
        OpenRouteServiceMatrix("secret-key", request_json=request_json).distances(
            origin=(144.9631, -37.8136),
            destinations=((144.9652, -37.8098),),
        )


def test_matrix_maps_not_found_to_ors_error():
    def request_json(url, body, headers, timeout):
        raise OpenRouteServiceNotFound("no walking route")

    with pytest.raises(OpenRouteServiceError, match="HTTP error"):
        OpenRouteServiceMatrix("secret-key", request_json=request_json).distances(
            origin=(144.9631, -37.8136),
            destinations=((144.9652, -37.8098),),
        )
