import json
from pathlib import Path

from src.ingestion.pandas_adapter import (
    normalize_hourly_counts,
    normalize_landmarks,
    normalize_minute_counts,
    normalize_sensors,
)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "pipeline"


def _records(name):
    import csv

    with (FIXTURE_DIR / name).open(newline="", encoding="utf-8-sig") as fixture:
        return list(csv.DictReader(fixture))


def _expectations(dataset):
    document = json.loads((FIXTURE_DIR / "expectations.json").read_text())
    return document[dataset]["target"]


def test_sensor_normalizer_ports_cleaning_and_uses_last_duplicate():
    result = normalize_sensors(_records("sensor_locations.csv"))
    expected = _expectations("sensor_locations")

    assert len(result["records"]) == expected["row_count"]
    assert [record["location_id"] for record in result["records"]] == expected["location_ids"]
    assert result["records"][0]["sensor_name"] == "Library North"
    assert result["records"][1]["latitude"] is None
    assert result["records"][1]["installation_date"] is None
    assert result["duplicates_resolved"] == 1
    assert result["rejected_count"] == 1
    assert result["rejected"][0]["code"] == "MISSING_LOCATION_ID"


def test_minute_normalizer_keeps_observations_only_and_last_duplicate():
    result = normalize_minute_counts(_records("minute_counts.csv"))
    expected = _expectations("minute_counts")

    assert len(result["records"]) == expected["row_count"]
    assert result["records"][0]["total_count"] == expected["duplicate_last_total"]
    assert all(record["is_imputed"] is False for record in result["records"])
    assert {record["location_id"] for record in result["records"]} == {1, 2}
    assert result["duplicates_resolved"] == 1
    assert result["rejected_count"] == 0


def test_minute_normalizer_accepts_live_api_shape_and_localizes_datetime():
    result = normalize_minute_counts(
        [
            {
                "location_id": 4,
                "sensing_date": "2026-12-15",
                "sensing_time": "14:17",
                "direction_1": 2,
                "direction_2": 3,
                "total_of_directions": 5,
            }
        ]
    )

    assert result["records"][0]["sensing_datetime"] == "2026-12-15T14:17:00+11:00"


def test_minute_normalizer_rejects_invalid_required_values_without_stopping_batch():
    records = _records("minute_counts.csv")[:1]
    records.append(
        {
            "Location_ID": "invalid",
            "Sensing_DateTime": "not-a-timestamp",
            "Total_of_Directions": "invalid",
        }
    )

    result = normalize_minute_counts(records)

    assert len(result["records"]) == 1
    assert result["rejected_count"] == 1
    assert result["rejected"][0]["index"] == 1
    assert result["rejected"][0]["code"] == "INVALID_LOCATION_ID"


def test_hourly_normalizer_preserves_first_duplicate_and_melbourne_dst():
    result = normalize_hourly_counts(_records("hourly_counts.csv"))
    expected = _expectations("hourly_counts")

    assert len(result["records"]) == expected["row_count"]
    assert [record["sensing_datetime"] for record in result["records"]] == expected["timestamps"]
    assert result["records"][0]["total_count"] == 100
    assert result["duplicates_resolved"] == 1
    assert result["rejected_count"] == 0


def test_hourly_normalizer_shifts_nonexistent_dst_hour_forward():
    result = normalize_hourly_counts(
        [
            {
                "Location_ID": 1,
                "Sensing_Date": "2026-10-04",
                "HourDay": 2,
                "Total_of_Directions": 10,
            }
        ]
    )

    assert result["records"][0]["sensing_datetime"] == "2026-10-04T03:00:00+11:00"


def test_hourly_normalizer_accepts_live_api_pedestrian_count():
    result = normalize_hourly_counts(
        [
            {
                "location_id": 9,
                "sensing_date": "2026-08-01",
                "hourday": 6,
                "direction_1": 28,
                "direction_2": 191,
                "pedestriancount": 219,
            }
        ]
    )

    assert result["rejected_count"] == 0
    assert result["records"][0]["total_count"] == 219


def test_landmark_normalizer_preserves_raw_categories_duplicates_and_null_coordinates():
    result = normalize_landmarks(_records("landmarks.csv"))
    expected = _expectations("landmarks")

    assert len(result["records"]) == expected["landmark_count"]
    assert result["rejected_count"] == 1
    assert result["duplicates_resolved"] == 0
    assert [record["feature_name"] for record in result["records"]].count("Flagstaff Gardens") == 2
    assert result["records"][3]["latitude"] is None
    assert {record["refuge_category"] for record in result["records"]} == {
        "LIBRARY",
        "MUSEUM",
        "GARDEN",
        "PARK",
    }
    assert {(record["theme"], record["sub_theme"]) for record in result["records"]} >= {
        ("Community Use", "Library"),
        ("Place of Assembly", "Museum"),
        ("Leisure/Recreation", "Public Garden"),
    }


def test_landmark_normalizer_does_not_treat_car_parks_as_refuges():
    result = normalize_landmarks(
        [
            {
                "Theme": "Transport",
                "Sub Theme": "Car Park",
                "Feature Name": "CBD Parking",
                "Co-ordinates": "-37.81, 144.96",
            }
        ]
    )

    assert result["records"][0]["refuge_category"] is None
