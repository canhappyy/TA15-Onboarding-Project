from __future__ import annotations

from dataclasses import dataclass

from src.repositories.api import RefugeRecord
from src.services.refuge_search import RefugeSearchService


ORIGIN = (144.9631, -37.8136)


def refuge(
    landmark_id: int,
    *,
    name: str | None = None,
    category: str = "PARK",
    longitude: float = 144.9631,
    latitude: float = -37.8136,
) -> RefugeRecord:
    return RefugeRecord(
        landmark_id=landmark_id,
        name=name or f"Refuge {landmark_id}",
        category=category,
        theme="Leisure",
        sub_theme="park",
        latitude=latitude,
        longitude=longitude,
    )


class FakeLoader:
    def __init__(self, refuges):
        self.refuges = refuges
        self.calls = []

    def load(self, origin, category=None):
        self.calls.append((origin, category))
        return self.refuges


class FakeMatrix:
    def __init__(self, distances):
        self.distances_to_return = distances
        self.calls = []

    def distances(self, *, origin, destinations):
        self.calls.append((origin, destinations))
        return self.distances_to_return


def test_search_returns_sorted_refuges_with_public_metadata_and_walking_navigation_url():
    loader = FakeLoader(
        [
            refuge(3, name="Zulu", longitude=144.9640),
            refuge(2, name="Alpha", longitude=144.9641),
            refuge(1, name="Alpha", longitude=144.9642),
        ]
    )
    matrix = FakeMatrix([500, 300, 300])

    results = RefugeSearchService(matrix, loader).search(ORIGIN, category="PARK")

    assert [result["id"] for result in results] == ["landmark-1", "landmark-2", "landmark-3"]
    assert results[0] == {
        "id": "landmark-1",
        "name": "Alpha",
        "category": "PARK",
        "coordinates": {"latitude": -37.8136, "longitude": 144.9642},
        "walkingDistanceKm": 0.3,
        "metadata": {"source": "City of Melbourne Open Data"},
        "navigationUrl": (
            "https://www.google.com/maps/dir/?api=1&destination=-37.8136%2C144.9642"
            "&travelmode=walking"
        ),
    }
    assert loader.calls == [(ORIGIN, "PARK")]
    assert matrix.calls == [
        (
                ORIGIN,
                (
                    (144.964, -37.8136),
                    (144.9641, -37.8136),
                    (144.9642, -37.8136),
                ),
            )
        ]


def test_search_preselects_fifty_nearest_straight_line_candidates_before_one_matrix_call():
    candidates = [
        refuge(
            index,
            longitude=ORIGIN[0] + index * 0.00001,
        )
        for index in range(1, 56)
    ]
    matrix = FakeMatrix([100] * 50)

    results = RefugeSearchService(matrix, FakeLoader(candidates)).search(ORIGIN)

    assert len(matrix.calls) == 1
    assert len(matrix.calls[0][1]) == 50
    assert matrix.calls[0][1] == tuple(
        (ORIGIN[0] + index * 0.00001, ORIGIN[1]) for index in range(1, 51)
    )
    assert len(results) == 20
    assert all(int(result["id"].removeprefix("landmark-")) <= 50 for result in results)


def test_search_omits_unreachable_and_over_one_kilometre_walking_results():
    candidates = [
        refuge(1, longitude=144.9640),
        refuge(2, longitude=144.9641),
        refuge(3, longitude=144.9642),
    ]
    matrix = FakeMatrix([None, 1000, 1000.01])

    results = RefugeSearchService(matrix, FakeLoader(candidates)).search(ORIGIN)

    assert [result["id"] for result in results] == ["landmark-2"]
    assert results[0]["walkingDistanceKm"] == 1.0


def test_search_does_not_send_straight_line_candidates_beyond_one_kilometre_to_matrix():
    near = refuge(1, longitude=144.964)
    far = refuge(2, longitude=144.983)
    matrix = FakeMatrix([100])

    results = RefugeSearchService(matrix, FakeLoader([far, near])).search(ORIGIN)

    assert [result["id"] for result in results] == ["landmark-1"]
    assert matrix.calls[0][1] == ((144.964, -37.8136),)


def test_search_returns_empty_without_matrix_call_when_no_candidate_is_in_radius():
    matrix = FakeMatrix([])

    results = RefugeSearchService(
        matrix,
        FakeLoader([refuge(1, longitude=144.983)]),
    ).search(ORIGIN)

    assert results == []
    assert matrix.calls == []
