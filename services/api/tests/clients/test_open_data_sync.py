import json
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from src.clients.open_data_sync import (
    HOURLY_COUNTS_DATASET,
    LANDMARKS_DATASET,
    MINUTE_COUNTS_DATASET,
    SENSOR_LOCATIONS_DATASET,
    OpenDataSyncClient,
    OpenDataSyncError,
    OpenDataSyncResponseError,
    OpenDataSyncTimeout,
    _request_json,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "open_data" / "responses.json"
)


@pytest.fixture
def source_records():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class StubTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, params, timeout):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return deepcopy(response)


def payload(*records, total_count=None):
    return {
        "total_count": len(records) if total_count is None else total_count,
        "results": list(records),
    }


def test_dataset_identifiers_match_official_sources():
    assert SENSOR_LOCATIONS_DATASET == "pedestrian-counting-system-sensor-locations"
    assert MINUTE_COUNTS_DATASET == (
        "pedestrian-counting-system-past-hour-counts-per-minute"
    )
    assert HOURLY_COUNTS_DATASET == (
        "pedestrian-counting-system-monthly-counts-per-hour"
    )
    assert LANDMARKS_DATASET == (
        "landmarks-and-places-of-interest-including-schools-theatres-health-services-spor"
    )


@pytest.mark.parametrize(
    ("method_name", "dataset_id", "fixture_name"),
    [
        ("fetch_sensors", SENSOR_LOCATIONS_DATASET, "sensors"),
        ("fetch_landmarks", LANDMARKS_DATASET, "landmarks"),
    ],
)
def test_static_sources_use_official_dataset_ids(
    method_name, dataset_id, fixture_name, source_records
):
    transport = StubTransport(payload(source_records[fixture_name]))
    client = OpenDataSyncClient(request_json=transport)

    records = getattr(client, method_name)()

    assert records == [source_records[fixture_name]]
    assert transport.calls == [
        {
            "url": client.records_url(dataset_id),
            "params": {"limit": 100, "offset": 0},
            "timeout": 15,
        }
    ]


def test_static_source_paginates_until_total_count():
    first_page = [{"location_id": value} for value in range(100)]
    second_page = [{"location_id": 100}]
    transport = StubTransport(
        payload(*first_page, total_count=101),
        payload(*second_page, total_count=101),
    )

    records = OpenDataSyncClient(request_json=transport).fetch_sensors()

    assert len(records) == 101
    assert [call["params"]["offset"] for call in transport.calls] == [0, 100]


def test_minute_source_uses_checkpoint_overlap(source_records):
    transport = StubTransport(payload(source_records["minute"]))
    client = OpenDataSyncClient(request_json=transport)
    watermark = datetime(2026, 8, 7, 13, 55, tzinfo=timezone.utc)

    records = client.fetch_minute_counts(
        watermark=watermark,
        overlap=timedelta(minutes=30),
    )

    assert records == [source_records["minute"]]
    assert transport.calls[0]["url"] == client.records_url(MINUTE_COUNTS_DATASET)
    assert transport.calls[0]["params"] == {
        "limit": 100,
        "offset": 0,
        "where": "sensing_datetime >= date'2026-08-07T13:25:00Z'",
        "order_by": "sensing_datetime ASC",
    }


def test_minute_source_without_checkpoint_anchors_to_latest_record(source_records):
    latest = source_records["minute"]
    transport = StubTransport(payload(latest), payload(latest))
    client = OpenDataSyncClient(request_json=transport)

    records = client.fetch_minute_counts()

    assert records == [latest]
    assert transport.calls[0]["params"] == {
        "limit": 1,
        "order_by": "sensing_datetime DESC",
    }
    assert transport.calls[1]["params"]["where"] == (
        "sensing_datetime >= date'2026-08-07T13:25:00Z'"
    )


def test_empty_minute_source_returns_without_window_request():
    transport = StubTransport(payload())

    assert OpenDataSyncClient(request_json=transport).fetch_minute_counts() == []
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    ("watermark", "overlap"),
    [
        (datetime(2026, 8, 7, 13, 55), timedelta(minutes=30)),
        (datetime(2026, 8, 7, 13, 55, tzinfo=timezone.utc), timedelta(seconds=-1)),
    ],
)
def test_minute_source_rejects_ambiguous_window(watermark, overlap):
    with pytest.raises(ValueError):
        OpenDataSyncClient(request_json=StubTransport()).fetch_minute_counts(
            watermark=watermark,
            overlap=overlap,
        )


def test_hourly_source_uses_daily_windows(source_records):
    first = dict(source_records["hourly"], sensing_date="2026-08-01")
    second = dict(source_records["hourly"], sensing_date="2026-08-02")
    transport = StubTransport(payload(first), payload(second))
    client = OpenDataSyncClient(request_json=transport)

    records = client.fetch_hourly_counts(date(2026, 8, 1), date(2026, 8, 3))

    assert records == [first, second]
    assert all(
        call["url"] == client.records_url(HOURLY_COUNTS_DATASET)
        for call in transport.calls
    )
    assert [call["params"]["where"] for call in transport.calls] == [
        "sensing_date >= date'2026-08-01' AND sensing_date < date'2026-08-02'",
        "sensing_date >= date'2026-08-02' AND sensing_date < date'2026-08-03'",
    ]
    assert all(
        call["params"]["order_by"] == "sensing_date ASC, hourday ASC, location_id ASC"
        for call in transport.calls
    )


def test_hourly_source_rejects_empty_or_reversed_range():
    client = OpenDataSyncClient(request_json=StubTransport())

    with pytest.raises(ValueError):
        client.fetch_hourly_counts(date(2026, 8, 1), date(2026, 8, 1))
    with pytest.raises(ValueError):
        client.fetch_hourly_counts(date(2026, 8, 2), date(2026, 8, 1))


@pytest.mark.parametrize("status_code", [429, 503])
def test_transient_http_error_retries_with_bounded_backoff(
    status_code, source_records
):
    sleeps = []
    unavailable = HTTPError("unused", status_code, "unavailable", {}, None)
    transport = StubTransport(unavailable, payload(source_records["sensors"]))

    records = OpenDataSyncClient(
        request_json=transport,
        sleep=sleeps.append,
    ).fetch_sensors()

    assert records == [source_records["sensors"]]
    assert len(transport.calls) == 2
    assert sleeps == [2]


def test_network_error_retries_then_maps_to_sanitized_error():
    sleeps = []
    transport = StubTransport(
        URLError("private network detail"),
        URLError("private network detail"),
        URLError("private network detail"),
    )

    with pytest.raises(OpenDataSyncError, match="request failed") as captured:
        OpenDataSyncClient(
            request_json=transport,
            sleep=sleeps.append,
        ).fetch_sensors()

    assert "private network detail" not in str(captured.value)
    assert len(transport.calls) == 3
    assert sleeps == [2, 4]


def test_timeout_retries_then_raises_timeout_error():
    transport = StubTransport(TimeoutError(), TimeoutError(), TimeoutError())

    with pytest.raises(OpenDataSyncTimeout):
        OpenDataSyncClient(request_json=transport, sleep=lambda _delay: None).fetch_sensors()

    assert len(transport.calls) == 3


def test_permanent_http_error_is_not_retried():
    transport = StubTransport(HTTPError("unused", 404, "missing", {}, None))

    with pytest.raises(OpenDataSyncError, match="rejected"):
        OpenDataSyncClient(request_json=transport).fetch_sensors()

    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "bad_payload",
    [
        [],
        {},
        {"total_count": 1, "results": "bad"},
        {"total_count": -1, "results": []},
        {"total_count": True, "results": []},
        {"total_count": 1, "results": ["bad record"]},
    ],
)
def test_client_rejects_malformed_response_shapes(bad_payload):
    with pytest.raises(OpenDataSyncResponseError, match="malformed"):
        OpenDataSyncClient(request_json=StubTransport(bad_payload)).fetch_sensors()


def test_default_transport_rejects_malformed_json(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"{"

    monkeypatch.setattr("src.clients.open_data_sync.urlopen", lambda *_args, **_kwargs: Response())

    with pytest.raises(OpenDataSyncResponseError, match="malformed JSON"):
        _request_json("https://example.invalid", {}, 15)


def test_client_has_no_heavy_or_database_dependencies():
    import src.clients.open_data_sync as client_module

    source = Path(client_module.__file__).read_text(encoding="utf-8")
    for dependency in ("pandas", "numpy", "sqlalchemy", "requests", "psycopg"):
        assert dependency not in source
