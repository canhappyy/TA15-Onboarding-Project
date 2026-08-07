"""
Ingest minute-level ("near-real-time") pedestrian counts ->
pedestrian_minute_count.

Gap-handling rule (confirmed, load-bearing for US1.2): a minute with NO
row for an active sensor means "no reading = zero pedestrians", not
"missing data". For every timestamp present in the source file, we
densify against the full set of active sensors and zero-fill any that
didn't report, flagging those rows is_imputed=true.

Depends on ingest_sensor_locations having already been run.
"""
from sqlalchemy import create_engine, text
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from clients.open_data_client import fetch_minute_counts

def _active_sensor_ids(conn) -> list[int]:
    rows = conn.execute(
        text("SELECT location_id FROM sensor_location WHERE status = :status"),
        {"status": config.ACTIVE_SENSOR_STATUS},
    ).fetchall()
    if not rows:
        raise RuntimeError(
            "sensor_location is empty or has no active sensors -- "
            "run ingest_sensor_locations.py before this script."
        )
    return [r[0] for r in rows]


def load(source: str = "csv", csv_path=config.MINUTE_COUNTS_CSV, database_url: str = config.DATABASE_URL) -> dict:
    engine = create_engine(database_url)
    with engine.connect() as conn:
        active_ids = _active_sensor_ids(conn)

    if source == "csv":
        raw = pd.read_csv(
            csv_path, encoding="utf-8-sig",
            usecols=["Location_ID", "Sensing_DateTime", "Direction_1", "Direction_2",
                     "Total_of_Directions"],
        )
    elif source == "api":
        raw = fetch_minute_counts()
    else:
        raise ValueError(f"Unknown source: {source!r} (expected 'csv' or 'api')")

    raw = raw.rename(
        columns={
            "Location_ID": "location_id",
            "Sensing_DateTime": "sensing_datetime",
            "Direction_1": "direction_1_count",
            "Direction_2": "direction_2_count",
            "Total_of_Directions": "total_count",
        }
    )
    before = len(raw)
    raw = raw.drop_duplicates(subset=["sensing_datetime", "location_id"], keep="last")
    dropped = before - len(raw)
    if dropped:
        print(f"pedestrian_minute_count: resolved {dropped} conflicting duplicate readings (kept latest)")

    timestamps = raw["sensing_datetime"].unique()

    grid = pd.MultiIndex.from_product(
        [timestamps, active_ids], names=["sensing_datetime", "location_id"]
    ).to_frame(index=False)

    densified = grid.merge(raw, on=["sensing_datetime", "location_id"], how="left")
    densified["is_imputed"] = densified["total_count"].isna()
    for col in ["direction_1_count", "direction_2_count", "total_count"]:
        densified[col] = densified[col].fillna(0).astype(int)

    if source == "csv":
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM pedestrian_minute_count"))
            densified.to_sql("pedestrian_minute_count", conn, if_exists="append", index=False)
    else:
        # Live run - upsert only, never wipe existing history. Requires a
        # UNIQUE constraint on (location_id, sensing_datetime) in schema.sql.
        with engine.begin() as conn:
            densified.to_sql("pedestrian_minute_count_staging", conn, if_exists="replace", index=False)
            conn.execute(text("""
                INSERT INTO pedestrian_minute_count
                    (location_id, sensing_datetime, direction_1_count, direction_2_count, total_count, is_imputed)
                SELECT location_id, sensing_datetime::timestamptz, direction_1_count, direction_2_count, total_count, is_imputed FROM pedestrian_minute_count_staging          
                ON CONFLICT (sensing_datetime, location_id) DO UPDATE SET
                    direction_1_count = EXCLUDED.direction_1_count,
                    direction_2_count = EXCLUDED.direction_2_count,
                    total_count = EXCLUDED.total_count,
                    is_imputed = EXCLUDED.is_imputed;
            """))
            conn.execute(text("DROP TABLE pedestrian_minute_count_staging;"))

    imputed = int(densified["is_imputed"].sum())
    print(
        f"pedestrian_minute_count: loaded {len(densified)} rows (source={source}) "
        f"({len(timestamps)} timestamps x {len(active_ids)} active sensors), "
        f"{imputed} zero-filled for gaps ({imputed / len(densified):.1%})"
    )
    return {"rows": len(densified), "timestamps": len(timestamps),
            "active_sensors": len(active_ids), "imputed": imputed, "source": source}



if __name__ == "__main__":
    load()
