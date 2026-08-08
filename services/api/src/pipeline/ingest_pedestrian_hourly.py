"""
Ingest hourly pedestrian counts -> pedestrian_hourly_count.

Source: pedestrian-counting-system-monthly-counts-per-hour.csv (daily
batch updates, ~1.6M rows -- streamed in chunks).

Gap handling: unlike the minute-level feed, this is an official daily
batch export where an absent (location_id, hour) combination usually
means the sensor was offline for that hour, not "zero pedestrians" -- so
we do NOT fabricate rows here. We log sensor-days short of 24 hourly
readings as a data-quality signal instead.
"""
from sqlalchemy import create_engine, text
import pandas as pd
from zoneinfo import ZoneInfo

import config

CHUNK_SIZE = 200_000
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")

def _prepare_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk = chunk.rename(
        columns={
            "Location_ID": "location_id",
            "Direction_1": "direction_1_count",
            "Direction_2": "direction_2_count",
            "Total_of_Directions": "total_count",
        }
    )

    # Build a naive local timestamp from the date + hour columns, then
    # localize with real Melbourne DST rules (AEST/+10:00 vs AEDT/+11:00)
    # instead of a hardcoded offset -- matches the approach in
    # clients/open_data_client.py for the minute-level feed.
    naive_local = pd.to_datetime(
        chunk["Sensing_Date"]).dt.strftime("%Y-%m-%d")
    naive_local = pd.to_datetime(
        naive_local + " " + chunk["HourDay"].astype(int).astype(str).str.zfill(2) + ":00:00"
    )
    localized = naive_local.dt.tz_localize(
        MELBOURNE_TZ, ambiguous=True, nonexistent="shift_forward"
    )
    chunk["sensing_datetime"] = localized.apply(lambda ts: ts.isoformat())

    return chunk[
        ["location_id", "sensing_datetime", "direction_1_count", "direction_2_count", "total_count"]
    ]


def _backfill_unknown_sensors(engine, location_ids: set[int]) -> int:
    """
    Historical count data can reference sensors no longer in the current
    metadata snapshot (decommissioned sensors, most likely). Rather than
    silently drop that pedestrian data or relax the FK, insert a minimal
    stub sensor_location row so referential integrity holds and the
    history is queryable -- flagged Status='D' so the scoring/UI layer
    can tell it apart from a live sensor.
    """
    with engine.begin() as conn:
        known = {
            r[0] for r in conn.execute(text("SELECT location_id FROM sensor_location")).fetchall()
        }
        missing = location_ids - known
        if not missing:
            return 0
        for loc_id in sorted(missing):
            conn.execute(
                text(
                    """
                    INSERT INTO sensor_location (location_id, sensor_name, status)
                    VALUES (:loc_id, :name, 'D')
                    ON CONFLICT (location_id) DO NOTHING
                    """
                ),
                {"loc_id": int(loc_id), "name": f"Unknown (historical, ID {loc_id})"},
            )
    return len(missing)


def load(csv_path=config.HOURLY_COUNTS_CSV, database_url: str = config.DATABASE_URL,
         chunksize: int = CHUNK_SIZE) -> dict:
    engine = create_engine(database_url)
    total_rows = 0
    coverage = {}

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM pedestrian_hourly_count"))

    # First pass: find any Location_IDs in the counts file that aren't in
    # sensor_location yet, and backfill stub rows for them so the FK on
    # pedestrian_hourly_count doesn't reject legitimate historical data.
    seen_location_ids = set()
    for chunk in pd.read_csv(csv_path, encoding="utf-8-sig", usecols=["Location_ID"], chunksize=chunksize):
        seen_location_ids |= set(chunk["Location_ID"])
    backfilled = _backfill_unknown_sensors(engine, seen_location_ids)
    if backfilled:
        print(f"  backfilled {backfilled} sensor_location stub row(s) for decommissioned/unknown sensors "
              f"referenced only in historical counts")

    for chunk in pd.read_csv(
        csv_path, encoding="utf-8-sig", chunksize=chunksize,
        usecols=["Location_ID", "Sensing_Date", "HourDay",
                 "Direction_1", "Direction_2", "Total_of_Directions"],
    ):
        for date, loc, hour in zip(chunk["Sensing_Date"], chunk["Location_ID"], chunk["HourDay"]):
            coverage.setdefault((loc, date), set()).add(int(hour))

        prepared = _prepare_chunk(chunk)
        prepared = prepared.drop_duplicates(subset=["location_id", "sensing_datetime"])
        with engine.begin() as conn:
            prepared.to_sql("pedestrian_hourly_count", conn, if_exists="append", index=False)
        total_rows += len(prepared)

    incomplete_days = sum(1 for hours in coverage.values() if len(hours) < 24)
    print(
        f"pedestrian_hourly_count: loaded {total_rows} rows across "
        f"{len(coverage)} sensor-days ({incomplete_days} sensor-days with "
        f"< 24 hourly readings -- gaps left as-is, not zero-filled)"
    )
    return {"rows": total_rows, "sensor_days": len(coverage), "incomplete_days": incomplete_days}


if __name__ == "__main__":
    load()
