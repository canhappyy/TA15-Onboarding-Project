from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode


def make_api_gateway_v2_event(
    *,
    method: str = "GET",
    path: str = "/",
    query: Mapping[str, str] | None = None,
    body: Any = None,
) -> dict[str, Any]:
    query_parameters = dict(query) if query else None

    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": urlencode(query_parameters or {}),
        "headers": {},
        "queryStringParameters": query_parameters,
        "requestContext": {"http": {"method": method, "path": path}},
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


def decode_lambda_response(response: Mapping[str, Any]) -> tuple[int, Mapping[str, str], Any]:
    return response["statusCode"], response.get("headers", {}), json.loads(response["body"])
