"""
Runs the full ClearWay data pipeline end to end, in dependency order.

Usage:
    python run_pipeline.py [--reset]
"""
import argparse
import time

import build_schema
import ingest_landmarks
import ingest_pedestrian_hourly
import ingest_pedestrian_minute
import ingest_sensor_locations


def main(reset: bool = False) -> None:
    steps = [
        ("Schema", lambda: build_schema.build_schema(reset=reset)),
        ("Sensor locations", ingest_sensor_locations.load),
        ("Minute counts (near-real-time)", ingest_pedestrian_minute.load),
        ("Hourly counts", ingest_pedestrian_hourly.load),
        ("Landmarks / refuges", ingest_landmarks.load),
    ]
    for name, fn in steps:
        start = time.time()
        print(f"\n--- {name} ---")
        fn()
        print(f"  ({time.time() - start:.1f}s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    main(reset=args.reset)
