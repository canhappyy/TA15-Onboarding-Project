"""
Leankit task 1 -- Build database schema from the ERD (PostgreSQL).

Usage:
    python build_schema.py [--reset]
"""
import argparse

from sqlalchemy import create_engine, text

import config

DROP_STATEMENTS = """
DROP TABLE IF EXISTS landmark CASCADE;
DROP TABLE IF EXISTS landmark_category CASCADE;
DROP TABLE IF EXISTS theme CASCADE;
DROP TABLE IF EXISTS pedestrian_minute_count CASCADE;
DROP TABLE IF EXISTS pedestrian_hourly_count CASCADE;
DROP TABLE IF EXISTS sensor_location CASCADE;
"""


def build_schema(reset: bool = False, database_url: str = config.DATABASE_URL) -> None:
    engine = create_engine(database_url)
    with engine.begin() as conn:
        if reset:
            conn.execute(text(DROP_STATEMENTS))
        schema_sql = config.SCHEMA_PATH.read_text()
        conn.execute(text(schema_sql))
    print(f"Schema ready at {database_url.split('@')[-1]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop tables before creating")
    args = parser.parse_args()
    build_schema(reset=args.reset)
