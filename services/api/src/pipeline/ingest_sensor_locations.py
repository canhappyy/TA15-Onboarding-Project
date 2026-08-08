"""
Ingest sensor metadata -> sensor_location.

Source: pedestrian-counting-system-sensor-locations.csv
Small, occasional-update file. Full replace on each run.
"""
from sqlalchemy import create_engine, text
import pandas as pd

import config
from transforms import transform_sensors


def load(csv_path=config.SENSOR_LOCATIONS_CSV, database_url: str = config.DATABASE_URL) -> int:
    result = transform_sensors(pd.read_csv(csv_path, encoding="utf-8-sig"))
    df = pd.DataFrame.from_records(result["records"])

    if result["rejected_count"]:
        print(f"  dropped {result['rejected_count']} invalid sensor row(s)")
    if result["duplicates_resolved"]:
        print(
            f"  {result['duplicates_resolved']} duplicate location_id row(s), "
            "keeping the last occurrence"
        )

    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sensor_location"))
        df.to_sql("sensor_location", conn, if_exists="append", index=False)

    active = (df["status"] == config.ACTIVE_SENSOR_STATUS).sum()
    print(f"sensor_location: loaded {len(df)} sensors ({active} active)")
    return len(df)


if __name__ == "__main__":
    load()
