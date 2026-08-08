from dataclasses import dataclass
from importlib import import_module
import math

import pytest


ROUTE = [(144.96, -37.82), (144.96, -37.80)]
MELBOURNE_LATITUDE = -37.81
METRES_PER_LONGITUDE_DEGREE = 111_320 * math.cos(
    math.radians(MELBOURNE_LATITUDE)
)
EXPLANATION = (
    "Calculated using pedestrian crowd information and nearby refuge "
    "availability."
)


@dataclass(frozen=True)
class Sensor:
    location_id: int
    name: str
    latitude: float
    longitude: float
    live_60_minute_total: int | None = 10
    historical_hourly_mean: float | None = 10.0
    historical_hourly_p75: float | None = 20.0


@dataclass(frozen=True)
class Refuge:
    landmark_id: int
    latitude: float
    longitude: float


@pytest.fixture
def scoring():
    try:
        return import_module("src.scoring.route")
    except ModuleNotFoundError:
        pytest.fail("Route scoring module is not implemented")


def longitude_offset(metres):
    return metres / METRES_PER_LONGITUDE_DEGREE


def sensor_at_distance(location_id, metres, **overrides):
    values = {
        "location_id": location_id,
        "name": f"Sensor {location_id}",
        "latitude": MELBOURNE_LATITUDE,
        "longitude": 144.96 + longitude_offset(metres),
    }
    values.update(overrides)
    return Sensor(**values)


def refuge_at_distance(landmark_id, metres):
    return Refuge(
        landmark_id=landmark_id,
        latitude=MELBOURNE_LATITUDE,
        longitude=144.96 + longitude_offset(metres),
    )


def test_distance_to_route_uses_nearest_segment_and_endpoint(scoring):
    on_segment = scoring.distance_to_route_metres(
        latitude=MELBOURNE_LATITUDE,
        longitude=144.96,
        route_coordinates=ROUTE,
    )
    east = scoring.distance_to_route_metres(
        latitude=MELBOURNE_LATITUDE,
        longitude=144.96 + longitude_offset(100),
        route_coordinates=ROUTE,
    )
    beyond_endpoint = scoring.distance_to_route_metres(
        latitude=-37.799,
        longitude=144.96,
        route_coordinates=ROUTE,
    )

    assert on_segment == pytest.approx(0, abs=0.01)
    assert east == pytest.approx(100, abs=0.2)
    assert beyond_endpoint == pytest.approx(111.2, abs=0.5)


def test_route_matches_every_sensor_within_100_metres(scoring):
    sensors = [
        sensor_at_distance(3, 100.5),
        sensor_at_distance(2, 99.5),
        sensor_at_distance(1, 20),
    ]

    result = scoring.score_route(ROUTE, sensors, [])

    assert [sensor.location_id for sensor in result.matched_sensors] == [1, 2]
    assert result.matched_sensors[1].distance_metres == pytest.approx(99.5, abs=0.2)


def test_route_uses_nearest_three_within_500_when_none_are_within_100(scoring):
    sensors = [
        sensor_at_distance(4, 450),
        sensor_at_distance(1, 150),
        sensor_at_distance(5, 501),
        sensor_at_distance(3, 350),
        sensor_at_distance(2, 250),
    ]

    result = scoring.score_route(ROUTE, sensors, [])

    assert [sensor.location_id for sensor in result.matched_sensors] == [1, 2, 3]


def test_route_rejects_when_no_sensor_is_within_500_metres(scoring):
    with pytest.raises(scoring.ScoringDataUnavailable, match="No nearby sensors"):
        scoring.score_route(ROUTE, [sensor_at_distance(1, 501)], [])


def test_live_reading_is_preferred_and_threshold_equality_is_high(scoring):
    sensor = sensor_at_distance(
        1,
        0,
        live_60_minute_total=20,
        historical_hourly_mean=5,
        historical_hourly_p75=20,
    )

    result = scoring.score_route(ROUTE, [sensor], [])
    matched = result.matched_sensors[0]

    assert matched.reading_used == 20
    assert matched.threshold == 20
    assert matched.high is True
    assert matched.fallback_used is False
    assert result.fallback_used is False
    assert result.warning == "High pedestrian density is expected on this route."


def test_missing_live_reading_uses_historical_mean(scoring):
    sensor = sensor_at_distance(
        1,
        0,
        live_60_minute_total=None,
        historical_hourly_mean=12.5,
        historical_hourly_p75=20,
    )

    result = scoring.score_route(ROUTE, [sensor], [])
    matched = result.matched_sensors[0]

    assert matched.reading_used == 12.5
    assert matched.high is False
    assert matched.fallback_used is True
    assert result.fallback_used is True
    assert result.warning == (
        "Live pedestrian data is unavailable; historical averages were used."
    )


def test_formula_uses_high_ratio_and_refuge_coverage(scoring):
    sensors = [
        sensor_at_distance(1, 0, live_60_minute_total=30),
        sensor_at_distance(2, 10, live_60_minute_total=10),
    ]

    without_refuges = scoring.score_route(ROUTE, sensors, [])
    with_refuges = scoring.score_route(
        ROUTE,
        sensors,
        [
            refuge_at_distance(1, 20),
            refuge_at_distance(2, 40),
            refuge_at_distance(3, 60),
            refuge_at_distance(4, 251),
        ],
    )

    assert without_refuges.score == 58
    assert without_refuges.indicator == "HIGH"
    assert with_refuges.score == 43
    assert with_refuges.indicator == "LOW"
    assert with_refuges.refuges_within_250m == 3
    assert with_refuges.explanation == EXPLANATION


def test_score_rounds_half_up_and_high_starts_at_50(scoring):
    sensors = [
        sensor_at_distance(1, 0, live_60_minute_total=30),
        sensor_at_distance(2, 10, live_60_minute_total=10),
    ]
    two_refuges = [refuge_at_distance(1, 20), refuge_at_distance(2, 40)]

    rounded = scoring.score_route(ROUTE, sensors, two_refuges)
    threshold = scoring.indicator_for_score(50)

    assert rounded.score == 48
    assert rounded.indicator == "LOW"
    assert threshold == "HIGH"


def test_unscorable_sensor_is_reported_but_excluded_from_ratio(scoring):
    sensors = [
        sensor_at_distance(1, 0, live_60_minute_total=30),
        sensor_at_distance(
            2,
            10,
            live_60_minute_total=100,
            historical_hourly_mean=None,
            historical_hourly_p75=None,
        ),
    ]

    result = scoring.score_route(ROUTE, sensors, [])

    assert result.score == 100
    assert result.matched_sensors[1].reading_used == 100
    assert result.matched_sensors[1].threshold is None
    assert result.matched_sensors[1].high is None


def test_route_rejects_when_every_matched_sensor_is_unscorable(scoring):
    sensor = sensor_at_distance(
        1,
        0,
        live_60_minute_total=None,
        historical_hourly_mean=None,
        historical_hourly_p75=None,
    )

    with pytest.raises(scoring.ScoringDataUnavailable, match="baseline"):
        scoring.score_route(ROUTE, [sensor], [])


def test_sensor_input_order_does_not_change_score_or_matches(scoring):
    sensors = [
        sensor_at_distance(2, 50, live_60_minute_total=30),
        sensor_at_distance(1, 50, live_60_minute_total=10),
    ]

    first = scoring.score_route(ROUTE, sensors, [])
    second = scoring.score_route(ROUTE, list(reversed(sensors)), [])

    assert first == second
    assert [sensor.location_id for sensor in first.matched_sensors] == [1, 2]


@pytest.mark.parametrize(
    "route",
    [[], [(144.96, -37.81)], [(200, -37.81), (144.96, -37.80)]],
)
def test_invalid_route_geometry_is_rejected_without_scoring(scoring, route):
    with pytest.raises(ValueError, match="route"):
        scoring.score_route(route, [sensor_at_distance(1, 0)], [])
