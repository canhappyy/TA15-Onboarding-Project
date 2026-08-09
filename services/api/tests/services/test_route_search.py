from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from src.clients.open_route_service import OpenRouteServiceError, RouteCandidate
from src.repositories.api import RefugeRecord, SensorCondition
from src.services.route_search import RouteSearchDataUnavailable, RouteSearchService


BOUNDARY = {
    "type": "Polygon",
    "coordinates": [
        [[144.90, -37.86], [145.00, -37.86], [145.00, -37.77], [144.90, -37.77], [144.90, -37.86]]
    ],
}
NOW = datetime(2026, 8, 9, 2, 0, tzinfo=timezone.utc)
ORIGIN = (144.95, -37.82)
DESTINATION = (144.97, -37.80)


def candidate(offset, *, duration=600, distance=1000):
    return RouteCandidate(
        coordinates=(ORIGIN, (144.96 + offset, -37.81), DESTINATION),
        distance_metres=distance,
        duration_seconds=duration,
    )


def sensor(location_id=1, *, observed_at=NOW, longitude=144.96):
    return SensorCondition(
        location_id=location_id,
        name=f"Sensor {location_id}",
        latitude=-37.81,
        longitude=longitude,
        live_60_minute_total=10,
        latest_observed_at=observed_at,
        historical_hourly_mean=8,
        historical_hourly_p75=20,
    )


class FakeDirections:
    def __init__(self, alternatives, optional_routes=None):
        self.base = alternatives
        self.optional_routes = list(optional_routes or [])
        self.route_calls = []

    def alternatives(self, *, origin, destination):
        return self.base

    def route(self, **kwargs):
        self.route_calls.append(kwargs)
        if not self.optional_routes:
            raise OpenRouteServiceError("no optional route")
        result = self.optional_routes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeRepository:
    def __init__(self, sensors=None, refuges=None):
        self.sensors = sensors or [sensor()]
        self.refuges = refuges or []
        self.load_calls = []

    def load(self, reference_time, bounds=None):
        self.load_calls.append((reference_time, bounds))
        return self.sensors, self.refuges


@dataclass(frozen=True)
class Match:
    location_id: int
    high: bool | None = False


@dataclass(frozen=True)
class Score:
    score: int
    indicator: str
    fallback_used: bool = False
    matched_sensors: tuple[Match, ...] = (Match(1),)
    warning: str | None = None
    explanation: str = "Calculated using pedestrian crowd information and nearby refuge availability."


def score_by_midpoint(route, sensors, refuges):
    del sensors, refuges
    score = 20 if route[1][0] > 144.96 else 70
    return Score(score=score, indicator="LOW" if score < 50 else "HIGH")


def test_search_sorts_distinct_routes_by_score_then_duration_and_marks_first_recommended():
    directions = FakeDirections(
        [candidate(-0.001, duration=500), candidate(0.001, duration=700)]
    )
    repository = FakeRepository()
    service = RouteSearchService(
        directions,
        repository,
        BOUNDARY,
        score_function=score_by_midpoint,
    )

    routes = service.search(ORIGIN, DESTINATION, reference_time=NOW)

    assert [route["score"] for route in routes] == [20, 70]
    assert [route["recommended"] for route in routes] == [True, False]
    assert routes[0]["durationMinutes"] == 12
    assert routes[0]["walkingDistanceKm"] == 1.0
    assert routes[0]["geometry"]["type"] == "LineString"
    assert routes[0]["freshness"] == {
        "observedAt": "2026-08-09T02:00:00+00:00",
        "stale": False,
        "fallbackUsed": False,
    }
    assert repository.load_calls[0][0] == NOW
    assert len(repository.load_calls) == 1


def test_search_deduplicates_routes_and_uses_midpoint_fallback():
    base = candidate(0)
    detour = candidate(0.002, duration=750)
    directions = FakeDirections([base, base], [detour])
    service = RouteSearchService(
        directions,
        FakeRepository(),
        BOUNDARY,
        score_function=lambda route, sensors, refuges: Score(10, "LOW"),
    )

    routes = service.search(ORIGIN, DESTINATION, reference_time=NOW)

    assert len(routes) == 2
    assert directions.route_calls[0]["waypoints"]


def test_search_requests_avoidance_route_for_high_matched_sensors():
    high_score = Score(100, "HIGH", matched_sensors=(Match(1, True),))
    directions = FakeDirections([candidate(0), candidate(0.001)], [candidate(0.002)])
    service = RouteSearchService(
        directions,
        FakeRepository(),
        BOUNDARY,
        score_function=lambda route, sensors, refuges: high_score,
    )

    service.search(ORIGIN, DESTINATION, reference_time=NOW)

    polygon = directions.route_calls[0]["avoid_polygons"]
    assert polygon["type"] == "MultiPolygon"
    assert len(polygon["coordinates"][0][0]) == 13


def test_avoidance_multipolygon_merges_overlapping_sensor_buffers_without_losing_coverage():
    high_score = Score(
        100,
        "HIGH",
        matched_sensors=(Match(1, True), Match(2, True)),
    )
    repository = FakeRepository(
        sensors=[
            sensor(1, longitude=144.9600),
            sensor(2, longitude=144.9605),
        ]
    )
    directions = FakeDirections([candidate(0), candidate(0.001)], [candidate(0.002)])
    service = RouteSearchService(
        directions,
        repository,
        BOUNDARY,
        score_function=lambda route, sensors, refuges: high_score,
    )

    service.search(ORIGIN, DESTINATION, reference_time=NOW)

    polygon = directions.route_calls[0]["avoid_polygons"]
    assert len(polygon["coordinates"]) == 1
    ring = polygon["coordinates"][0][0]
    assert min(position[0] for position in ring) < 144.9594
    assert max(position[0] for position in ring) > 144.9610


def test_search_marks_old_or_missing_observation_stale_and_preserves_warning():
    stale_sensor = sensor(observed_at=NOW - timedelta(minutes=31))
    score = Score(
        80,
        "HIGH",
        fallback_used=True,
        warning="High pedestrian density is expected on this route.",
    )
    service = RouteSearchService(
        FakeDirections([candidate(0), candidate(0.001)]),
        FakeRepository(sensors=[stale_sensor]),
        BOUNDARY,
        score_function=lambda route, sensors, refuges: score,
    )

    routes = service.search(ORIGIN, DESTINATION, reference_time=NOW)

    assert routes[0]["freshness"]["stale"] is True
    assert routes[0]["freshness"]["fallbackUsed"] is True
    assert routes[0]["warning"] == (
        "High pedestrian density is expected on this route. "
        "Pedestrian data may be stale."
    )


def test_search_fails_when_two_distinct_scorable_routes_cannot_be_produced():
    service = RouteSearchService(
        FakeDirections([candidate(0)]),
        FakeRepository(),
        BOUNDARY,
        score_function=lambda route, sensors, refuges: Score(10, "LOW"),
    )

    with pytest.raises(RouteSearchDataUnavailable):
        service.search(ORIGIN, DESTINATION, reference_time=NOW)


def test_search_returns_maximum_three_and_uses_duration_as_score_tiebreaker():
    routes = [
        candidate(0.001, duration=900),
        candidate(0.002, duration=600),
        candidate(0.003, duration=700),
        candidate(0.004, duration=500),
    ]
    service = RouteSearchService(
        FakeDirections(routes),
        FakeRepository(),
        BOUNDARY,
        score_function=lambda route, sensors, refuges: Score(20, "LOW"),
    )

    results = service.search(ORIGIN, DESTINATION, reference_time=NOW)

    assert len(results) == 3
    assert [route["durationMinutes"] for route in results] == [9, 10, 12]


def test_observation_exactly_thirty_minutes_old_is_not_stale():
    service = RouteSearchService(
        FakeDirections([candidate(0), candidate(0.001)]),
        FakeRepository(sensors=[sensor(observed_at=NOW - timedelta(minutes=30))]),
        BOUNDARY,
        score_function=lambda route, sensors, refuges: Score(10, "LOW"),
    )

    results = service.search(ORIGIN, DESTINATION, reference_time=NOW)

    assert all(route["freshness"]["stale"] is False for route in results)
