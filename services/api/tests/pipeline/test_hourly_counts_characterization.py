import ingest_pedestrian_hourly

from tests.pipeline.conftest import FakeEngine


def test_hourly_loader_records_chunking_backfill_duplicates_and_melbourne_offsets(
    monkeypatch, capture_to_sql, pipeline_fixture_dir, pipeline_expectations
):
    engine = FakeEngine(select_rows=[(1,), (2,)])
    monkeypatch.setattr(ingest_pedestrian_hourly, "create_engine", lambda _url: engine)

    stats = ingest_pedestrian_hourly.load(
        pipeline_fixture_dir / "hourly_counts.csv",
        "postgresql://unused",
        chunksize=100,
    )

    frame = capture_to_sql[0]["frame"].sort_values(
        ["location_id", "sensing_datetime"]
    ).reset_index(drop=True)
    expected = pipeline_expectations["hourly_counts"]["legacy"]
    statements = "\n".join(sql for sql, _ in engine.connection.statements)

    assert stats["rows"] == expected["row_count"]
    assert "DELETE FROM pedestrian_hourly_count" in statements
    assert "Unknown (historical, ID 99)" in str(engine.connection.statements)
    assert frame["sensing_datetime"].tolist() == expected["timestamps"]
