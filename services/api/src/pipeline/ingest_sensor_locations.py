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
    df = df[keep_cols].drop_duplicates(subset="location_id", keep="last")

    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sensor_location"))
        df.to_sql("sensor_location", conn, if_exists="append", index=False)

    active = (df["status"] == config.ACTIVE_SENSOR_STATUS).sum()
    print(f"sensor_location: loaded {len(df)} sensors ({active} active)")
    return len(df)


if __name__ == "__main__":
    load()
