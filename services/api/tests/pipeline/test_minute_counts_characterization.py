import pandas as pd

import ingest_pedestrian_minute

from tests.pipeline.conftest import FakeEngine


def test_csv_minute_loader_records_duplicate_zero_imputation_and_delete(
    monkeypatch, capture_to_sql, pipeline_fixture_dir, pipeline_expectations
):
    engine = FakeEngine(select_rows=[(1,), (2,), (3,)])
    monkeypatch.setattr(ingest_pedestrian_minute, "create_engine", lambda _url: engine)

    stats = ingest_pedestrian_minute.load(
        source="csv",
        csv_path=pipeline_fixture_dir / "minute_counts.csv",
        database_url="postgresql://unused",
    )

    frame = capture_to_sql[0]["frame"].sort_values("location_id").reset_index(drop=True)
    expected = pipeline_expectations["minute_counts"]["legacy"]

    assert stats["rows"] == expected["row_count"]
    assert stats["imputed"] == expected["imputed_count"]
    assert "DELETE FROM pedestrian_minute_count" in engine.connection.statements[1][0]
    assert frame.loc[frame["location_id"] == 1, "total_count"].item() == expected["duplicate_last_total"]
    imputed = frame.loc[frame["location_id"] == 3].iloc[0]
    assert imputed["total_count"] == 0
    assert bool(imputed["is_imputed"]) is True


def test_api_minute_loader_records_staging_upsert_without_target_delete(
    monkeypatch, capture_to_sql, pipeline_fixture_dir
):
    engine = FakeEngine(select_rows=[(1,), (2,)])
    api_frame = pd.read_csv(pipeline_fixture_dir / "minute_counts.csv")
    monkeypatch.setattr(ingest_pedestrian_minute, "create_engine", lambda _url: engine)
    monkeypatch.setattr(ingest_pedestrian_minute, "fetch_minute_counts", lambda: api_frame)

    ingest_pedestrian_minute.load(source="api", database_url="postgresql://unused")

    statements = "\n".join(sql for sql, _ in engine.connection.statements)
    assert capture_to_sql[0]["table"] == "pedestrian_minute_count_staging"
    assert "ON CONFLICT (sensing_datetime, location_id) DO UPDATE" in statements
    assert "DELETE FROM pedestrian_minute_count" not in statements
