import pytest

from src.clients.open_route_service import (
    OpenRouteServiceError,
    OpenRouteServiceGeocoder,
    OpenRouteServiceTimeout,
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

    assert captured["url"] == "https://api.openrouteservice.org/geocode/search"
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

