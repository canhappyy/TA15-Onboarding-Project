import pytest

from tests.api_helpers import decode_lambda_response, make_api_gateway_v2_event


@pytest.fixture
def api_gateway_v2_event_factory():
    return make_api_gateway_v2_event


@pytest.fixture
def lambda_response_decoder():
    return decode_lambda_response

