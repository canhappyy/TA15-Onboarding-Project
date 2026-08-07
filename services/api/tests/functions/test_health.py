import json

from src.functions.health.handler import lambda_handler


def test_health_response_remains_outside_common_envelope():
    response = lambda_handler({}, None)

    assert response["statusCode"] == 200
    assert response["headers"] == {"Content-Type": "application/json"}
    assert json.loads(response["body"]) == {"status": "ok"}
