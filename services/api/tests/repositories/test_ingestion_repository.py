from datetime import datetime, timezone

import pytest

from src.repositories.ingestion import (
    IngestionCheckpoint,
    IngestionRepository,
    WriteStats,
)


class FakeCursor:
    def __init__(self):
        self.statements = []
        self.batches = []
        self.outcomes = []
        self.fetchone_values = []
        self.fetchall_values = []
        self.outcome_index = 0
        self.batch_results_active = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters=None):
        self.statements.append((str(statement), parameters))

    def executemany(self, statement, parameters, returning=False):
        self.batches.append((str(statement), list(parameters), returning))
        self.outcome_index = 0
        self.batch_results_active = returning

    def nextset(self):
        if self.outcome_index >= len(self.outcomes) - 1:
            return None
        self.outcome_index += 1
        return True

    def fetchone(self):
        if self.batch_results_active:
            return (self.outcomes[self.outcome_index],)
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def fetchall(self):
        return self.fetchall_values.pop(0) if self.fetchall_values else []


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.commit_called = False
        self.rollback_called = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.commit_called = True

    def rollback(self):
        self.rollback_called = True


def test_sensor_upsert_returns_insert_update_counts_without_committing():
    cursor = FakeCursor()
    cursor.outcomes = [True, False]
    connection = FakeConnection(cursor)
    repository = IngestionRepository(connection)

    stats = repository.upsert_sensors(
        [
            {"location_id": 1, "sensor_name": "One", "status": "A"},
            {"location_id": 2, "sensor_name": "Two", "status": "A"},
        ]
    )

    statement, parameters, returning = cursor.batches[0]
    assert "ON CONFLICT (location_id) DO UPDATE" in statement
    assert len(parameters) == 2
    assert returning is True
    assert stats == WriteStats(inserted=1, updated=1)
    assert connection.commit_called is False
    assert connection.rollback_called is False


@pytest.mark.parametrize(
    ("method_name", "table_name", "conflict_key"),
    [
        ("upsert_minute_counts", "pedestrian_minute_count", "sensing_datetime, location_id"),
        ("upsert_hourly_counts", "pedestrian_hourly_count", "location_id, sensing_datetime"),
    ],
)
def test_count_upserts_use_composite_keys(method_name, table_name, conflict_key):
    cursor = FakeCursor()
    cursor.outcomes = [True]
    repository = IngestionRepository(FakeConnection(cursor))
    record = {
        "location_id": 1,
        "sensing_datetime": "2026-08-04T00:17:00+10:00",
        "direction_1_count": 2,
        "direction_2_count": 3,
        "total_count": 5,
        "is_imputed": False,
    }

    stats = getattr(repository, method_name)([record])
    statement = cursor.batches[0][0]

    assert f"INSERT INTO {table_name}" in statement
    assert f"ON CONFLICT ({conflict_key}) DO UPDATE" in statement
    assert stats == WriteStats(inserted=1, updated=0)


def test_landmark_upsert_preserves_raw_category_and_uses_natural_key():
    cursor = FakeCursor()
    cursor.fetchone_values = [(10,), (20,)]
    cursor.outcomes = [True]
    repository = IngestionRepository(FakeConnection(cursor))

    stats = repository.upsert_landmarks(
        [
            {
                "theme": "Community Use",
                "sub_theme": "Library",
                "feature_name": "City Library",
                "latitude": -37.8175,
                "longitude": 144.9652,
            }
        ]
    )

    statements = "\n".join(statement for statement, _ in cursor.statements)
    landmark_statement, landmark_parameters, returning = cursor.batches[0]
    assert "ON CONFLICT (theme, sub_theme)" in statements
    assert "ON CONFLICT (theme_id, category_name)" in statements
    assert cursor.statements[1][1][1] == "Library"
    assert "ON CONFLICT (category_id, feature_name, latitude, longitude)" in landmark_statement
    assert landmark_parameters[0]["category_id"] == 20
    assert returning is True
    assert stats == WriteStats(inserted=1, updated=0)


def test_checkpoint_round_trip_uses_dataset_key_without_committing():
    cursor = FakeCursor()
    started_at = datetime(2026, 8, 8, 1, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 8, 8, 1, 1, tzinfo=timezone.utc)
    checkpoint = IngestionCheckpoint(
        dataset="minute",
        watermark=completed_at,
        last_started_at=started_at,
        last_completed_at=completed_at,
        status="succeeded",
        inserted_count=4,
        updated_count=2,
        rejected_count=1,
        duplicates_resolved=3,
        error_message=None,
    )
    cursor.fetchone_values = [
        (
            checkpoint.dataset,
            checkpoint.watermark,
            checkpoint.last_started_at,
            checkpoint.last_completed_at,
            checkpoint.status,
            checkpoint.inserted_count,
            checkpoint.updated_count,
            checkpoint.rejected_count,
            checkpoint.duplicates_resolved,
            checkpoint.error_message,
        )
    ]
    connection = FakeConnection(cursor)
    repository = IngestionRepository(connection)

    repository.save_checkpoint(checkpoint)
    loaded = repository.read_checkpoint("minute")

    statements = "\n".join(statement for statement, _ in cursor.statements)
    assert "ON CONFLICT (dataset) DO UPDATE" in statements
    assert loaded == checkpoint
    assert connection.commit_called is False


def test_empty_upserts_are_no_ops():
    cursor = FakeCursor()
    repository = IngestionRepository(FakeConnection(cursor))

    assert repository.upsert_sensors([]) == WriteStats(0, 0)
    assert repository.upsert_minute_counts([]) == WriteStats(0, 0)
    assert repository.upsert_hourly_counts([]) == WriteStats(0, 0)
    assert repository.upsert_landmarks([]) == WriteStats(0, 0)
    assert cursor.batches == []


def test_existing_sensor_ids_queries_only_requested_ids():
    cursor = FakeCursor()
    cursor.fetchall_values = [[(1,), (3,)]]
    repository = IngestionRepository(FakeConnection(cursor))

    result = repository.read_existing_sensor_ids({1, 2, 3})

    statement, parameters = cursor.statements[0]
    assert "FROM sensor_location" in statement
    assert "location_id = ANY(%s)" in statement
    assert parameters == ([1, 2, 3],)
    assert result == {1, 3}


def test_existing_sensor_ids_empty_input_is_no_op():
    cursor = FakeCursor()
    repository = IngestionRepository(FakeConnection(cursor))

    assert repository.read_existing_sensor_ids(set()) == set()
    assert cursor.statements == []
