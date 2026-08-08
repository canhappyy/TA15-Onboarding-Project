import pandas as pd

import ingest_landmarks

from tests.pipeline.conftest import FakeEngine


def test_coordinate_parser_records_valid_and_invalid_shapes():
    assert ingest_landmarks._parse_coords(" -37.81, 144.96 ") == (-37.81, 144.96)
    assert ingest_landmarks._parse_coords("not coordinates") == (None, None)
    assert ingest_landmarks._parse_coords(None) == (None, None)


def test_landmark_loader_records_categories_duplicates_and_destructive_refresh(
    monkeypatch, capture_to_sql, pipeline_fixture_dir, pipeline_expectations
):
    engine = FakeEngine()
    monkeypatch.setattr(ingest_landmarks, "create_engine", lambda _url: engine)

    stats = ingest_landmarks.load(
        pipeline_fixture_dir / "landmarks.csv", "postgresql://unused"
    )

    expected = pipeline_expectations["landmarks"]["legacy"]
    statements = "\n".join(sql for sql, _ in engine.connection.statements)
    category_frame = next(
        write["frame"] for write in capture_to_sql if write["table"] == "landmark_category"
    )
    landmark_frame = next(
        write["frame"] for write in capture_to_sql if write["table"] == "landmark"
    )

    assert stats["landmarks"] == expected["landmark_count"]
    assert int(category_frame["is_refuge"].sum()) == expected["refuge_category_count"]
    assert landmark_frame["feature_name"].tolist().count("Flagstaff Gardens") == 2
    assert pd.isna(
        landmark_frame.loc[landmark_frame["feature_name"] == "City Museum", "latitude"].item()
    )
    assert "DELETE FROM landmark" in statements
    assert "ALTER SEQUENCE theme_theme_id_seq RESTART WITH 1" in statements
