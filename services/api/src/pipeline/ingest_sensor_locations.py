"""
Ingest sensor metadata -> sensor_location.

Source: pedestrian-counting-system-sensor-locations.csv
Small, occasional-update file. Full replace on each run.
"""
from sqlalchemy import create_engine, text
import pandas as pd

import config


def load(csv_path=config.SENSOR_LOCATIONS_CSV, database_url: str = config.DATABASE_URL) -> int:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    df = df.rename(
        columns={
            "Location_ID": "location_id",
            "Sensor_Description": "sensor_description",
            "Sensor_Name": "sensor_name",
            "Installation_Date": "installation_date",
            "Note": "note",
            "Location_Type": "location_type",
            "Status": "status",
            "Direction_1": "direction_1_label",
            "Direction_2": "direction_2_label",
            "Latitude": "latitude",
            "Longitude": "longitude",
        }
    )

    keep_cols = [
        "location_id", "sensor_description", "sensor_name", "installation_date",
        "note", "location_type", "status", "direction_1_label", "direction_2_label",
        "latitude", "longitude",
    ]
    df = df[keep_cols]

    # --- data cleaning -------------------------------------------------
    # Strip whitespace on text columns used for filtering/comparison
    # elsewhere (status especially -- config.ACTIVE_SENSOR_STATUS does an
    # exact string match, and a stray trailing space would silently make
    # an active sensor look inactive with no error raised anywhere).
    for col in ["sensor_description", "sensor_name", "note", "location_type",
                "status", "direction_1_label", "direction_2_label"]:
        df[col] = df[col].astype("string").str.strip()

    # A row with no location_id can't go in (it's the primary key) --
    # drop rather than let the insert fail opaquely, and say so.
    before = len(df)
    df = df.dropna(subset=["location_id"])
    if len(df) < before:
        print(f"  dropped {before - len(df)} row(s) with missing location_id")
    df["location_id"] = df["location_id"].astype(int)
 
    # Coerce numeric/date columns -- bad values become NULL instead
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    bad_coords = df["latitude"].isna() | df["longitude"].isna()
    if bad_coords.any():
        print(f"  {bad_coords.sum()} sensor(s) missing/unparseable lat-lon "
              f"(kept, but distance-based features like nearby-refuge lookups won't work for them)")
 
    parsed_dates = pd.to_datetime(df["installation_date"], errors="coerce")
    bad_dates = parsed_dates.isna() & df["installation_date"].notna()
    if bad_dates.any():
        print(f"  {bad_dates.sum()} sensor(s) had an unparseable installation_date, set to NULL")
    df["installation_date"] = parsed_dates.dt.date
 
    duplicate_count = df.duplicated(subset="location_id", keep="last").sum()
    if duplicate_count:
        print(f"  {duplicate_count} duplicate location_id row(s), keeping the last occurrence")
    df = df.drop_duplicates(subset="location_id", keep="last")

    # --------------------------------------------------------------------
    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sensor_location"))
        df.to_sql("sensor_location", conn, if_exists="append", index=False)

    active = (df["status"] == config.ACTIVE_SENSOR_STATUS).sum()
    print(f"sensor_location: loaded {len(df)} sensors ({active} active)")
    return len(df)


if __name__ == "__main__":
    load()
