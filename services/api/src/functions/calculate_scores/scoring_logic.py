"""
Gives each sensor a High or Low score, based on its own past data.
Each sensor has its own threshold, not one fixed number for all.

Includes both the DB fetch functions and the scoring functions,
since scoring always needs data fetched first.

Fetchs functions accept:
  - a single int   -> one sensor
  - a list of ints -> all sensors along one route
  - None           -> every sensor

Uses config.py from services/api/src/pipeline/
"""
 

import sys
from pathlib import Path
from typing import Any, Optional, Union

from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
 
LocationId = Optional[Union[int, list, tuple, set]]


# Finds and imports config.py from the pipeline folder 
# so no duplicate copy for the DB connection settings.
def _load_config():
    pipeline_path = Path(__file__).resolve().parents[2] / "pipeline"
    if str(pipeline_path) not in sys.path:
        sys.path.insert(0, str(pipeline_path))
    import config
    return config
 

# Changes location_id (int, list, or None) into a SQL filter and its parameter values
def _location_filter(location_id: LocationId) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}
    if location_id is None:
        return "", params
    if isinstance(location_id, (list, tuple, set)):
        params["location_ids"] = list(location_id)
        return "AND location_id = ANY(:location_ids)", params
    params["location_id"] = location_id
    return "AND location_id = :location_id", params




# ------------------------------------------------------------
# Fetching data
# ------------------------------------------------------------
# Reads data from Postgres, which was loaded by ingest_*.py
# Gets historical hourly counts and uses for the threshold
def fetch_hourly_history(
    location_id: LocationId = None,
    database_url: Optional[str] = None,
) -> pd.DataFrame:
    if database_url is None:
        config = _load_config()
        database_url = config.DATABASE_URL
    engine = create_engine(str(database_url))

    where_clause, params = _location_filter(location_id)
    query = text(f"""
        SELECT location_id, sensing_datetime, total_count
        FROM pedestrian_hourly_count
        WHERE sensing_datetime > NOW() - INTERVAL '90 days' 
        {where_clause}
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params=params)
 
 
# Gets recent minute-level counts and uses for the current reading
def fetch_recent_minutes(
    location_id: LocationId = None,
    hours_back: int = 1,
    database_url: Optional[str] = None,
) -> pd.DataFrame:
    """Get recent minute-level counts, used for the current reading."""
    if database_url is None:
        config = _load_config()
        database_url = config.DATABASE_URL
    engine = create_engine(str(database_url))
 
    where_clause, params = _location_filter(location_id)
    params["hours_back"] = hours_back
    query = text(f"""
        SELECT location_id, sensing_datetime, total_count, is_imputed
        FROM pedestrian_minute_count
        WHERE sensing_datetime > NOW() - (:hours_back || ' hours')::interval
        AND is_imputed = false
        {where_clause}
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params=params)
    



# ------------------------------------------------------------
# Calculating the scores
# ------------------------------------------------------------
# Find each sensor's threshold (top 25% of hourly counts)
def calculate_thresholds(
    hourly_history: pd.DataFrame,
    count_col: str = "total_count",
    quantile: float = 0.75,
) -> pd.DataFrame:
    return (
        hourly_history.groupby("location_id")[count_col]
        .quantile(quantile)
        .reset_index()
        .rename(columns={count_col: "threshold"})
    )
 

# Sum the last 60 minutes per sensor, so it matches the hourly threshold.
def get_last_hour_total(
    live_minutes: pd.DataFrame,
    count_col: str = "total_count",
    datetime_col: str = "sensing_datetime",
    reference_time: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    df = live_minutes.copy()
    df[datetime_col] = pd.to_datetime(df[datetime_col])
 
    if reference_time is None:
        ref_time = df[datetime_col].max()
    else:
        ref_time = reference_time
    window_start = ref_time - pd.Timedelta(hours=1)
 
    recent = df[(df[datetime_col] > window_start) & (df[datetime_col] <= ref_time)]
 
    return (
        recent.groupby("location_id")[count_col]
        .sum()
        .reset_index()
        .rename(columns={count_col: "current_count"})
    )
 

# Compare current count to threshold
# If missing falls back to historical average 
# Note: observed_at is None when no observation timestamp is available
def classify_current_conditions(
    thresholds: pd.DataFrame,
    current_readings: pd.DataFrame,
    hourly_history: pd.DataFrame,
    count_col: str = "total_count",
    observed_at: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    merged = thresholds.merge(current_readings, on="location_id", how="left")

    historical_avg = (
        hourly_history.groupby("location_id")[count_col]
        .mean()
        .reset_index()
        .rename(columns={count_col: "historical_avg"})
    )
    merged = merged.merge(historical_avg, on="location_id", how="left")

    merged["used_fallback"] = merged["current_count"].isna()
    merged["reading_used"] = merged["current_count"].fillna(merged["historical_avg"])
    merged["level"] = np.where(merged["reading_used"] >= merged["threshold"], "High", "Low")
    merged["observed_at"] = np.where(merged["used_fallback"], None, observed_at)

    return merged[["location_id", "reading_used", "threshold", "level", "used_fallback", "observed_at"]]


# ------------------------------------------------------------
# Sensory Score = crowd level + nearby refuge availability
# (the original spec: "combining pedestrian density + refuge
# availability", not crowd density alone -- `level` above is
# congestion only. This adds a separate `sensory_level` column
# without changing what `level` means, so nothing that already
# depends on `level` breaks.)
# ------------------------------------------------------------
def fetch_sensor_coordinates(
    location_id: LocationId = None,
    database_url: Optional[str] = None,
) -> pd.DataFrame:
    if database_url is None:
        config = _load_config()
        database_url = config.DATABASE_URL
    engine = create_engine(str(database_url))

    where_clause, params = _location_filter(location_id)
    query = text(f"""
        SELECT location_id, latitude, longitude
        FROM sensor_location
        WHERE 1=1 {where_clause}
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params=params)


def fetch_refuge_landmarks(database_url: Optional[str] = None) -> pd.DataFrame:
    """Only landmarks already flagged is_refuge = true at ingest time."""
    if database_url is None:
        config = _load_config()
        database_url = config.DATABASE_URL
    engine = create_engine(str(database_url))

    query = text("""
        SELECT l.latitude, l.longitude
        FROM landmark l
        JOIN landmark_category c ON c.category_id = l.category_id
        WHERE c.is_refuge = true
          AND l.latitude IS NOT NULL AND l.longitude IS NOT NULL
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn)


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    import math
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def add_sensory_level(
    scored: pd.DataFrame,
    sensor_coords: pd.DataFrame,
    refuges: pd.DataFrame,
    radius_m: float = 300,
) -> pd.DataFrame:
    """
    sensory_level = level ("congestion"), downgraded from High to Low if
    a refuge is within radius_m -- a High-crowd spot with an easy nearby
    escape route is less sensory-taxing, even though it's still busy.
    This 300m radius and "any nearby refuge fully cancels High" rule are
    judgment calls, not something the brief specified -- confirm with
    the team before treating this as final.
    """
    df = scored.merge(sensor_coords, on="location_id", how="left")

    def has_nearby_refuge(row) -> bool:
        if pd.isna(row["latitude"]) or pd.isna(row["longitude"]):
            return False
        for _, r in refuges.iterrows():
            if pd.isna(r["latitude"]) or pd.isna(r["longitude"]):
                continue
            if _haversine_m(row["latitude"], row["longitude"], r["latitude"], r["longitude"]) <= radius_m:
                return True
        return False

    df["refuge_nearby"] = df.apply(has_nearby_refuge, axis=1)
    df["sensory_level"] = np.where(
        (df["level"] == "High") & (~df["refuge_nearby"]), "High", "Low"
    )
    return df.drop(columns=["latitude", "longitude"])


# ------------------------------------------------------------
# Shortcut: fetch + score
# ------------------------------------------------------------
def get_scores(location_id: LocationId = None, database_url: Optional[str] = None) -> pd.DataFrame:
    hourly_history = fetch_hourly_history(location_id, database_url)
    live_minutes = fetch_recent_minutes(location_id, database_url=database_url)

    reference_time = pd.Timestamp.now(tz="UTC")

    thresholds = calculate_thresholds(hourly_history)
    current_readings = get_last_hour_total(live_minutes, reference_time=reference_time)
    scored = classify_current_conditions(
        thresholds, current_readings, hourly_history, observed_at=reference_time
    )

    # Everything below this line is unchanged -- calling their functions
    # exactly as they wrote them, no modifications to their code
    sensor_coords = fetch_sensor_coordinates(location_id, database_url)
    refuges = fetch_refuge_landmarks(database_url)
    return add_sensory_level(scored, sensor_coords, refuges)