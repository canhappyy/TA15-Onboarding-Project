import pandas as pd

import ingest_sensor_locations

from tests.pipeline.conftest import FakeEngine


def test_sensor_loader_records_current_cleaning_and_delete_behavior(
    monkeypatch, capture_to_sql, pipeline_fixture_dir, pipeline_expectations
):
    engine = FakeEngine()
    monkeypatch.setattr(ingest_sensor_locations, "create_engine", lambda _url: engine)

    loaded = ingest_sensor_locations.load(
        pipeline_fixture_dir / "sensor_locations.csv", "postgresql://unused"
    )

    written = capture_to_sql[0]
    frame = written["frame"].sort_values("location_id").reset_index(drop=True)
    expected = pipeline_expectations["sensor_locations"]["legacy"]

    assert loaded == expected["row_count"]
    assert written["table"] == "sensor_location"
    assert "DELETE FROM sensor_location" in engine.connection.statements[0][0]
    assert frame["location_id"].tolist() == expected["location_ids"]
    assert frame.loc[frame["location_id"] == 1, "sensor_name"].item() == "Library North"
    assert pd.isna(frame.loc[frame["location_id"] == 2, "latitude"].item())
    assert pd.isna(frame.loc[frame["location_id"] == 2, "installation_date"].item())
