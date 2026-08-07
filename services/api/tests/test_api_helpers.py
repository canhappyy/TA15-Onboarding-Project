def test_api_gateway_v2_event_factory_builds_query_and_json_body(api_gateway_v2_event_factory):
    event = api_gateway_v2_event_factory(
        method="POST",
        path="/routes/search",
        query={"mode": "walking"},
        body={"origin": {"latitude": -37.81, "longitude": 144.96}},
    )

    assert event["version"] == "2.0"
    assert event["routeKey"] == "POST /routes/search"
    assert event["rawQueryString"] == "mode=walking"
    assert event["queryStringParameters"] == {"mode": "walking"}
    assert event["requestContext"]["http"] == {
        "method": "POST",
        "path": "/routes/search",
    }
    assert event["body"] == '{"origin": {"latitude": -37.81, "longitude": 144.96}}'
    assert event["isBase64Encoded"] is False


def test_lambda_response_decoder_returns_status_headers_and_json(lambda_response_decoder):
    response = {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": '{"success": true, "data": {"value": 1}}',
    }

    assert lambda_response_decoder(response) == (
        200,
        {"Content-Type": "application/json"},
        {"success": True, "data": {"value": 1}},
    )

