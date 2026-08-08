import run_pipeline


def test_pipeline_dependency_order(monkeypatch):
    calls = []
    monkeypatch.setattr(run_pipeline.build_schema, "build_schema", lambda reset: calls.append("schema"))
    monkeypatch.setattr(run_pipeline.ingest_sensor_locations, "load", lambda: calls.append("sensors"))
    monkeypatch.setattr(run_pipeline.ingest_pedestrian_minute, "load", lambda: calls.append("minute"))
    monkeypatch.setattr(run_pipeline.ingest_pedestrian_hourly, "load", lambda: calls.append("hourly"))
    monkeypatch.setattr(run_pipeline.ingest_landmarks, "load", lambda: calls.append("landmarks"))

    run_pipeline.main(reset=False)

    assert calls == ["schema", "sensors", "minute", "hourly", "landmarks"]
