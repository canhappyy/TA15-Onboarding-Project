import json
import os
from unittest.mock import patch

from src.clients.open_route_service import OpenRouteServiceError, OpenRouteServiceTimeout
from src.functions.location_search.handler import (
    SecretsManagerApiKeyReader,
    lambda_handler,
)


SERVICE_BOUNDARY = {
    "type": "Polygon",
    "coordinates": [
        [[144.90, -37.86], [145.00, -37.86], [145.00, -37.77], [144.90, -37.77], [144.90, -37.86]]
    ],
}


class FakeSecretReader:
    def __init__(self, api_key="secret-key", error=None):
        self.api_key = api_key
        self.error = error
        self.requested_arn = None

    def get_api_key(self, secret_arn):
        self.requested_arn = secret_arn
        if self.error:
            raise self.error
        return self.api_key


class FakeGeocoder:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    def search(self, text, *, bounds, limit=10):
        self.calls.append({"text": text, "bounds": bounds, "limit": limit})
        if self.error:
            raise self.error
        return self.results


class FakeSecretsManagerClient:
    def __init__(self, secret_string):
        self.secret_string = secret_string

    def get_secret_value(self, SecretId):
        return {"SecretString": self.secret_string}


def event(text=None):
    query = None if text is None else {"text": text}
    return {"queryStringParameters": query}


def decode(response):
    return response["statusCode"], json.loads(response["body"])


def candidate(identifier, longitude, latitude):
    return {
        "id": identifier,
        "label": f"Location {identifier}",
        "coordinates": {"longitude": longitude, "latitude": latitude},
    }


def invoke(search_event, *, geocoder=None, secret_reader=None):
    environment = {"ORS_API_KEY_SECRET_ARN": "arn:aws:secretsmanager:mock"}
    with patch.dict(os.environ, environment, clear=True):
        return lambda_handler(
            search_event,
            None,
            secret_reader=secret_reader or FakeSecretReader(),
            geocoder=geocoder or FakeGeocoder(),
            boundary_geometry=SERVICE_BOUNDARY,
        )


def test_returns_at_most_five_in_boundary_suggestions():
    results = [candidate(str(index), 144.95, -37.81) for index in range(6)]
    results.append(candidate("outside", 145.10, -37.81))
    geocoder = FakeGeocoder(results=results)

    status, body = decode(invoke(event("library"), geocoder=geocoder))

    assert status == 200
    assert body["success"] is True
    assert len(body["data"]["suggestions"]) == 5
    assert [item["id"] for item in body["data"]["suggestions"]] == ["0", "1", "2", "3", "4"]
    assert geocoder.calls[0]["limit"] == 10


def test_rejects_empty_search_text_without_calling_upstream():
    geocoder = FakeGeocoder()

    status, body = decode(invoke(event("   "), geocoder=geocoder))

    assert status == 400
    assert body == {
        "success": False,
        "error": {"code": "INVALID_REQUEST", "message": "Search text is required."},
    }
    assert geocoder.calls == []


def test_returns_empty_success_when_upstream_has_no_matches():
    status, body = decode(invoke(event("not a real place")))

    assert status == 200
    assert body == {"success": True, "data": {"suggestions": []}}


def test_rejects_results_outside_service_area():
    geocoder = FakeGeocoder(results=[candidate("outside", 145.10, -37.81)])

    status, body = decode(invoke(event("Richmond"), geocoder=geocoder))

    assert status == 400
    assert body["error"]["code"] == "OUTSIDE_SERVICE_AREA"


def test_maps_upstream_timeout():
    geocoder = FakeGeocoder(error=OpenRouteServiceTimeout("timed out"))

    status, body = decode(invoke(event("library"), geocoder=geocoder))

    assert status == 504
    assert body["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_maps_malformed_upstream_response():
    geocoder = FakeGeocoder(error=OpenRouteServiceError("malformed response"))

    status, body = decode(invoke(event("library"), geocoder=geocoder))

    assert status == 502
    assert body["error"]["code"] == "UPSTREAM_ERROR"


def test_missing_secret_configuration_is_sanitized():
    with patch.dict(os.environ, {}, clear=True):
        status, body = decode(
            lambda_handler(
                event("library"),
                None,
                secret_reader=FakeSecretReader(),
                geocoder=FakeGeocoder(),
                boundary_geometry=SERVICE_BOUNDARY,
            )
        )

    assert status == 500
    assert body == {
        "success": False,
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Location search is temporarily unavailable.",
        },
    }


def test_missing_secret_value_is_sanitized():
    secret_reader = FakeSecretReader(error=ValueError("secret has no value"))

    status, body = decode(
        invoke(event("library"), secret_reader=secret_reader)
    )

    assert status == 500
    assert body["error"] == {
        "code": "INTERNAL_SERVER_ERROR",
        "message": "Location search is temporarily unavailable.",
    }


def test_secret_reader_accepts_json_api_key():
    reader = SecretsManagerApiKeyReader(
        client=FakeSecretsManagerClient('{"api_key":"secret-key"}')
    )

    assert reader.get_api_key("secret-arn") == "secret-key"
