import json
from typing import Any


JSON_HEADERS = {"Content-Type": "application/json"}


def success_response(data: Any, *, status_code: int = 200) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": JSON_HEADERS.copy(),
        "body": json.dumps({"success": True, "data": data}),
    }


def error_response(status_code: int, code: str, message: str) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": JSON_HEADERS.copy(),
        "body": json.dumps(
            {
                "success": False,
                "error": {"code": code, "message": message},
            }
        ),
    }
