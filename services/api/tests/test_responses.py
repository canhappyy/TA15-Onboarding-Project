import json

from src.common.responses import error_response, success_response


def test_success_response_returns_common_envelope():
    response = success_response({"routes": []}, status_code=201)

    assert response["statusCode"] == 201
    assert response["headers"] == {"Content-Type": "application/json"}
    assert json.loads(response["body"]) == {
        "success": True,
        "data": {"routes": []},
    }


def test_error_response_returns_common_envelope():
    response = error_response(
        400,
        "INVALID_REQUEST",
        "Origin is required.",
    )

    assert response["statusCode"] == 400
    assert response["headers"] == {"Content-Type": "application/json"}
    assert json.loads(response["body"]) == {
        "success": False,
        "error": {
            "code": "INVALID_REQUEST",
            "message": "Origin is required.",
        },
    }
