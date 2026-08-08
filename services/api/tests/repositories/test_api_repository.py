from datetime import datetime, timezone
from importlib import import_module

import pytest


REFERENCE_TIME = datetime(2026, 8, 9, 2, 0, tzinfo=timezone.utc)


class FakeCursor:
    def __init__(self, *, fetchone_values=None, fetchall_values=None):
        self.statements = []
        self.fetchone_values = list(fetchone_values or [])
        self.fetchall_values = list(fetchall_values or [])

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters=None):
        self.statements.append((str(statement), parameters))

    def fetchone(self):
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def fetchall(self):
        return self.fetchall_values.pop(0) if self.fetchall_values else []


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.commit_called = False
        self.rollback_called = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.commit_called = True

    def rollback(self):
        self.rollback_called = True


def api_repository_module():
    try:
        return import_module("src.repositories.api")
    except ModuleNotFoundError:
        pytest.fail("PostgreSQL API repository is not implemented")


def test_sensor_conditions_return_raw_live_history_and_freshness_values():
    module = api_repository_module()
    latest = datetime(2026, 8, 9, 1, 55, tzinfo=timezone.utc)
    cursor = FakeCursor(
        fetchall_values=[
            [
                (2, "Sensor Two", -37.82, 144.97, None, None, 15.0, 18.5),
                (1, "Sensor One", -37.81, 144.96, 42, latest, 25.0, 32.5),
            ]
        ]
    )
    connection = FakeConnection(cursor)
    repository = module.PostgresApiRepository(connection)

    result = repository.list_sensor_conditions(REFERENCE_TIME)

    assert result == [
        module.SensorCondition(
            location_id=1,
            name="Sensor One",
            latitude=-37.81,
            longitude=144.96,
            live_60_minute_total=42,
            latest_observed_at=latest,
            historical_hourly_mean=25.0,
            historical_hourly_p75=32.5,
        ),
        module.SensorCondition(
            location_id=2,
            name="Sensor Two",
            latitude=-37.82,
            longitude=144.97,
            live_60_minute_total=None,
            latest_observed_at=None,
            historical_hourly_mean=15.0,
            historical_hourly_p75=18.5,
        ),
    ]
    statement, parameters = cursor.statements[0]
    assert "status = 'A'" in statement
    assert "is_imputed = FALSE" in statement
    assert "INTERVAL '60 minutes'" in statement
    assert "INTERVAL '90 days'" in statement
    assert "percentile_cont(0.75)" in statement
    assert parameters == {"reference_time": REFERENCE_TIME}
    assert connection.commit_called is False
    assert connection.rollback_called is False


def test_sensor_conditions_apply_parameterized_bounding_box():
    module = api_repository_module()
    bounds = module.BoundingBox(
        south=-37.83,
        west=144.94,
        north=-37.80,
        east=144.99,
    )
    cursor = FakeCursor(fetchall_values=[[]])
    repository = module.PostgresApiRepository(FakeConnection(cursor))

    assert repository.list_sensor_conditions(REFERENCE_TIME, bounds) == []

    statement, parameters = cursor.statements[0]
    assert "latitude BETWEEN %(south)s AND %(north)s" in statement
    assert "longitude BETWEEN %(west)s AND %(east)s" in statement
    assert parameters == {
        "reference_time": REFERENCE_TIME,
        "south": -37.83,
        "west": 144.94,
        "north": -37.80,
        "east": 144.99,
    }


def test_sensor_conditions_require_timezone_aware_reference_time():
    module = api_repository_module()
    cursor = FakeCursor()
    repository = module.PostgresApiRepository(FakeConnection(cursor))

    with pytest.raises(ValueError, match="timezone-aware"):
        repository.list_sensor_conditions(datetime(2026, 8, 9, 2, 0))

    assert cursor.statements == []


def test_latest_minute_timestamp_excludes_imputed_rows():
    module = api_repository_module()
    latest = datetime(2026, 8, 9, 1, 58, tzinfo=timezone.utc)
    cursor = FakeCursor(fetchone_values=[(latest,)])
    repository = module.PostgresApiRepository(FakeConnection(cursor))

    assert repository.get_latest_minute_timestamp() == latest
    statement, parameters = cursor.statements[0]
    assert "MAX(sensing_datetime)" in statement
    assert "is_imputed = FALSE" in statement
    assert "JOIN sensor_location" in statement
    assert "sensor.status = 'A'" in statement
    assert "sensor.latitude IS NOT NULL" in statement
    assert "sensor.longitude IS NOT NULL" in statement
    assert parameters is None


def test_latest_minute_timestamp_returns_none_for_empty_table():
    module = api_repository_module()
    repository = module.PostgresApiRepository(
        FakeConnection(FakeCursor(fetchone_values=[(None,)]))
    )

    assert repository.get_latest_minute_timestamp() is None


def test_refuges_map_supported_subthemes_and_sort_results():
    module = api_repository_module()
    cursor = FakeCursor(
        fetchall_values=[
            [
                (4, "Flagstaff Park", "Leisure", "Public Park", -37.81, 144.95),
                (2, "Melbourne Museum", "Assembly", "Museum", -37.80, 144.97),
                (3, "Royal Garden", "Leisure", "Public Garden", -37.82, 144.98),
                (1, "City Library", "Community", "Library", -37.81, 144.96),
            ]
        ]
    )
    repository = module.PostgresApiRepository(FakeConnection(cursor))

    result = repository.list_refuges()

    assert [(record.category, record.name) for record in result] == [
        ("GARDEN", "Royal Garden"),
        ("LIBRARY", "City Library"),
        ("MUSEUM", "Melbourne Museum"),
        ("PARK", "Flagstaff Park"),
    ]
    statement, parameters = cursor.statements[0]
    assert "is_refuge = TRUE" in statement
    assert "latitude IS NOT NULL" in statement
    assert "longitude IS NOT NULL" in statement
    assert "LOWER(BTRIM(stored_theme.sub_theme))" in statement
    assert "ANY(%(subthemes)s)" in statement
    assert set(parameters["subthemes"]) >= {
        "library",
        "museum",
        "public garden",
        "public park",
    }


def test_refuges_deduplicate_categories_and_apply_bounds():
    module = api_repository_module()
    bounds = module.BoundingBox(-37.83, 144.94, -37.80, 144.99)
    cursor = FakeCursor(fetchall_values=[[]])
    repository = module.PostgresApiRepository(FakeConnection(cursor))

    assert repository.list_refuges(
        bounds=bounds,
        categories=["park", "PARK", "garden"],
    ) == []

    statement, parameters = cursor.statements[0]
    assert "latitude BETWEEN %(south)s AND %(north)s" in statement
    assert "longitude BETWEEN %(west)s AND %(east)s" in statement
    assert set(parameters["subthemes"]) == {
        "garden",
        "public garden",
        "park",
        "public park",
        "informal outdoor facility (park/garden/reserve)",
    }


def test_refuges_reject_unknown_category_without_querying():
    module = api_repository_module()
    cursor = FakeCursor()
    repository = module.PostgresApiRepository(FakeConnection(cursor))

    with pytest.raises(ValueError, match="Unsupported refuge category"):
        repository.list_refuges(categories=["CAFE"])

    assert cursor.statements == []


def test_refuges_empty_category_collection_is_no_op():
    module = api_repository_module()
    cursor = FakeCursor()
    repository = module.PostgresApiRepository(FakeConnection(cursor))

    assert repository.list_refuges(categories=[]) == []
    assert cursor.statements == []


def test_bounding_box_rejects_invalid_coordinate_order():
    module = api_repository_module()

    with pytest.raises(ValueError, match="south must not exceed north"):
        module.BoundingBox(-37.80, 144.94, -37.83, 144.99)


def test_repository_executes_read_only_sql():
    module = api_repository_module()
    cursor = FakeCursor(fetchone_values=[(None,)], fetchall_values=[[], []])
    repository = module.PostgresApiRepository(FakeConnection(cursor))

    repository.list_sensor_conditions(REFERENCE_TIME)
    repository.get_latest_minute_timestamp()
    repository.list_refuges()

    sql = "\n".join(statement.upper() for statement, _ in cursor.statements)
    for write_keyword in ("INSERT ", "UPDATE ", "DELETE ", "COMMIT", "ROLLBACK"):
        assert write_keyword not in sql
