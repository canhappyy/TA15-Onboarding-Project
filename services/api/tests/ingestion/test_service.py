from datetime import date, datetime, timedelta, timezone

import pytest

from src.ingestion.service import IngestionService
from src.repositories.ingestion import IngestionCheckpoint, WriteStats


NOW = datetime(2026, 8, 8, 12, tzinfo=timezone.utc)

SENSOR_ROWS = [
    {
        "location_id": 1,
        "sensor_name": "Sensor One",
        "status": "A",
        "latitude": -37.81,
        "longitude": 144.96,
    }
]
MINUTE_ROWS = [
    {
        "location_id": 1,
        "sensing_date": "2026-08-08",
        "sensing_time": "21:55",
        "total_of_directions": 5,
    }
]
HOURLY_ROWS = [
    {
        "location_id": 99,
        "sensing_date": "2026-08-07",
        "hourday": 8,
        "pedestriancount": 10,
    }
]
LANDMARK_ROWS = [
    {
        "theme": "Community Use",
        "sub_theme": "Library",
        "feature_name": "City Library",
        "co_ordinates": {"lat": -37.8175, "lon": 144.9652},
    }
]


class FakeClient:
    def __init__(self):
        self.calls = []

    def fetch_sensors(self):
        self.calls.append(("sensors",))
        return SENSOR_ROWS

    def fetch_minute_counts(self, watermark=None, overlap=timedelta(minutes=30)):
        self.calls.append(("minute", watermark, overlap))
        return MINUTE_ROWS

    def fetch_hourly_counts(self, start_date, end_date):
        self.calls.append(("hourly", start_date, end_date))
        return [dict(HOURLY_ROWS[0], sensing_date=start_date.isoformat())]

    def fetch_landmarks(self):
        self.calls.append(("landmarks",))
        return LANDMARK_ROWS


class Store:
    def __init__(self):
        self.checkpoints = {}
        self.sensor_ids = set()
        self.calls = []
        self.connections = []
        self.fail_on = None
        self.lock_available = True
        self.lock_held = False
        self.ingestion_status = {
            "tables": {
                "sensors": {"rows": 2, "active_with_coordinates": 1},
                "minute": {
                    "rows": 3,
                    "observed_rows": 3,
                    "imputed_rows": 0,
                    "latest_timestamp": NOW,
                },
                "hourly": {
                    "rows": 4,
                    "observed_rows": 4,
                    "imputed_rows": 0,
                    "latest_timestamp": NOW,
                },
                "landmarks": {
                    "rows": 5,
                    "refuge_rows": 4,
                    "refuges_by_category": {"LIBRARY": 1, "PARK": 3},
                },
            },
            "checkpoints": {
                "sensors": {
                    "status": "succeeded",
                    "watermark": NOW,
                    "last_completed_at": NOW,
                    "inserted_count": 2,
                    "updated_count": 0,
                    "rejected_count": 0,
                    "duplicates_resolved": 0,
                },
                "hourly": {},
                "minute": {},
                "landmarks": {},
            },
        }


class FakeConnection:
    def __init__(self, store):
        self.store = store
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, error_type, _error, _traceback):
        if error_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False


class FakeRepository:
    def __init__(self, connection):
        self.store = connection.store

    def read_checkpoint(self, dataset):
        self.store.calls.append(("read_checkpoint", dataset))
        return self.store.checkpoints.get(dataset)

    def read_ingestion_status(self):
        self.store.calls.append(("read_ingestion_status",))
        return self.store.ingestion_status

    def try_acquire_ingestion_lock(self):
        self.store.calls.append(("try_acquire_ingestion_lock",))
        if not self.store.lock_available:
            return False
        self.store.lock_held = True
        return True

    def release_ingestion_lock(self):
        self.store.calls.append(("release_ingestion_lock",))
        was_held = self.store.lock_held
        self.store.lock_held = False
        return was_held

    def read_existing_sensor_ids(self, location_ids):
        self.store.calls.append(("read_sensor_ids", set(location_ids)))
        return self.store.sensor_ids.intersection(location_ids)

    def upsert_sensors(self, records):
        records = list(records)
        self.store.calls.append(("upsert_sensors", records))
        self.store.sensor_ids.update(record["location_id"] for record in records)
        return WriteStats(inserted=len(records), updated=0)

    def upsert_minute_counts(self, records):
        return self._write("minute", records)

    def upsert_hourly_counts(self, records):
        return self._write("hourly", records)

    def upsert_landmarks(self, records):
        return self._write("landmarks", records)

    def save_checkpoint(self, checkpoint):
        self.store.calls.append(("save_checkpoint", checkpoint.dataset))
        self.store.checkpoints[checkpoint.dataset] = checkpoint

    def _write(self, dataset, records):
        records = list(records)
        self.store.calls.append((f"upsert_{dataset}", records))
        if self.store.fail_on == dataset:
            raise ValueError("private record detail")
        return WriteStats(inserted=len(records), updated=0)


def build_service(store=None, client=None):
    store = store or Store()
    client = client or FakeClient()

    def connection_factory():
        connection = FakeConnection(store)
        store.connections.append(connection)
        return connection

    return (
        IngestionService(
            client=client,
            connection_factory=connection_factory,
            repository_factory=FakeRepository,
            clock=lambda: NOW,
        ),
        store,
        client,
    )


def succeeded_checkpoint(dataset, watermark):
    return IngestionCheckpoint.succeeded(
        dataset=dataset,
        watermark=watermark,
        inserted_count=1,
        updated_count=0,
        rejected_count=0,
        duplicates_resolved=0,
        completed_at=NOW,
    )


def test_static_sync_writes_sensors_before_landmarks_with_checkpoints():
    service, store, client = build_service()

    result = service.run("static")

    assert client.calls == [("sensors",), ("landmarks",)]
    writes = [call[0] for call in store.calls if call[0].startswith("upsert_")]
    assert writes == ["upsert_sensors", "upsert_landmarks"]
    assert set(store.checkpoints) == {"sensors", "landmarks"}
    assert result["mode"] == "static"
    assert result["datasets"]["sensors"]["inserted"] == 1
    assert all(connection.committed for connection in store.connections)


def test_run_holds_one_advisory_lock_around_all_ingestion_work():
    service, store, _client = build_service()

    service.run("static")

    assert store.calls[0] == ("try_acquire_ingestion_lock",)
    assert store.calls[-1] == ("release_ingestion_lock",)
    assert store.lock_held is False


def test_concurrent_run_skips_without_downloads_or_writes():
    store = Store()
    store.lock_available = False
    service, store, client = build_service(store=store)

    result = service.run("minute")

    assert result == {
        "mode": "minute",
        "status": "skipped",
        "reason": "INGESTION_ALREADY_RUNNING",
        "datasets": {},
    }
    assert client.calls == []
    assert store.calls == [("try_acquire_ingestion_lock",)]
    assert len(store.connections) == 1


def test_status_is_read_only_serializable_and_bypasses_ingestion_lock():
    service, store, client = build_service()

    result = service.run("status")

    assert result["mode"] == "status"
    assert result["tables"]["minute"]["latest_timestamp"] == NOW.isoformat()
    assert (
        result["checkpoints"]["sensors"]["last_completed_at"]
        == NOW.isoformat()
    )
    assert client.calls == []
    assert store.calls == [("read_ingestion_status",)]


def test_static_sync_passes_required_refuge_classification_to_repository():
    service, store, _client = build_service()

    service.run("static")

    landmark_write = next(
        call for call in store.calls if call[0] == "upsert_landmarks"
    )
    assert landmark_write[1][0]["refuge_category"] == "LIBRARY"


def test_minute_sync_uses_checkpoint_overlap_and_commits_checkpoint_atomically():
    service, store, client = build_service()
    watermark = datetime(2026, 8, 8, 10, tzinfo=timezone.utc)
    store.checkpoints["minute"] = succeeded_checkpoint("minute", watermark)

    result = service.run("minute")

    assert client.calls == [("minute", watermark, timedelta(minutes=30))]
    assert store.checkpoints["minute"].watermark == "2026-08-08T21:55:00+10:00"
    assert result["datasets"]["minute"] == {
        "inserted": 1,
        "updated": 0,
        "rejected": 0,
        "duplicates_resolved": 0,
    }


def test_failed_batch_rolls_back_and_preserves_previous_checkpoint():
    service, store, _client = build_service()
    previous = succeeded_checkpoint(
        "minute", datetime(2026, 8, 8, 10, tzinfo=timezone.utc)
    )
    store.checkpoints["minute"] = previous
    store.fail_on = "minute"

    with pytest.raises(ValueError, match="private record detail"):
        service.run("minute")

    assert store.checkpoints["minute"] is previous
    assert store.connections[-1].rolled_back is True
    assert store.calls[-1] == ("release_ingestion_lock",)
    assert store.lock_held is False


def test_hourly_sync_backfills_unknown_sensor_inside_count_transaction():
    service, store, client = build_service()

    result = service.run("hourly")

    assert client.calls == [("hourly", date(2026, 8, 7), date(2026, 8, 8))]
    stub_call = next(
        call for call in store.calls if call[0] == "upsert_sensors"
    )
    assert stub_call[1] == [
        {
            "location_id": 99,
            "sensor_name": "Unknown historical sensor 99",
            "status": "I",
        }
    ]
    assert result["datasets"]["hourly"]["backfilled_sensors"] == 1
    assert store.checkpoints["hourly"].watermark.isoformat() == (
        "2026-08-07T14:00:00+00:00"
    )


def test_bootstrap_runs_sensors_90_hourly_days_minute_then_landmarks():
    service, store, client = build_service()

    result = service.run("bootstrap")

    assert client.calls[0] == ("sensors",)
    assert client.calls[-2][0] == "minute"
    assert client.calls[-1] == ("landmarks",)
    hourly_calls = [call for call in client.calls if call[0] == "hourly"]
    assert len(hourly_calls) == 90
    assert hourly_calls[0] == ("hourly", date(2026, 5, 10), date(2026, 5, 11))
    assert hourly_calls[-1] == ("hourly", date(2026, 8, 7), date(2026, 8, 8))
    assert result["datasets"]["hourly"]["inserted"] == 90
    assert set(store.checkpoints) == {"sensors", "hourly", "minute", "landmarks"}


def test_service_rejects_unknown_mode_without_side_effects():
    service, store, client = build_service()

    with pytest.raises(ValueError, match="Unsupported ingestion mode"):
        service.run("everything")

    assert client.calls == []
    assert store.connections == []
