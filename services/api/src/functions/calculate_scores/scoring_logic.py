"""
Gives each sensor a High or Low score, based on its own past data.
Each sensor has its own threshold, not one fixed number for all.

Includes both the DB fetch functions and the scoring functions,
since scoring always needs data fetched first.

Fetch functions accept:
  - a single int   -> one sensor
  - a list of ints -> sensors along one route
  - None           -> every sensor
"""
 

from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
 

# Changes location_id (int, list, or None) into a SQL filter and its parameter values
def _location_filter(location_id):
    if location_id is None:
        return "", {}
    if isinstance(location_id, (list, tuple, set)):
        return "AND location_id = ANY(:location_ids)", {"location_ids": list(location_id)}
    return "AND location_id = :location_id", {"location_id": location_id}




# ------------------------------------------------------------
# Fetching data
# ------------------------------------------------------------
# Reads data from Postgres, which was loaded by ingest_*.py
def fetch_hourly_history(location_id=None, database_url: str = None) -> pd.DataFrame:
    """Get historical hourly counts, used for the threshold."""
    import config
    database_url = database_url or config.DATABASE_URL
    engine = create_engine(database_url)
 
    where_clause, params = _location_filter(location_id)
    query = text(f"""
        SELECT location_id, sensing_datetime, total_count
        FROM pedestrian_hourly_count
        WHERE 1=1 {where_clause}
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params=params)
 
 
def fetch_recent_minutes(location_id=None, hours_back: int = 1, database_url: str = None) -> pd.DataFrame:
    """Get recent minute-level counts, used for the current reading."""
    import config
    database_url = database_url or config.DATABASE_URL
    engine = create_engine(database_url)
 
    where_clause, params = _location_filter(location_id)
    params["hours_back"] = hours_back
    query = text(f"""
        SELECT location_id, sensing_datetime, total_count, is_imputed
        FROM pedestrian_minute_count
        WHERE sensing_datetime > NOW() - (:hours_back || ' hours')::interval
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
    reference_time: pd.Timestamp = None,
) -> pd.DataFrame:
    df = live_minutes.copy()
    df[datetime_col] = pd.to_datetime(df[datetime_col])
 
    if reference_time is None:
        reference_time = df[datetime_col].max()
    window_start = reference_time - pd.Timedelta(hours=1)
 
    recent = df[(df[datetime_col] > window_start) & (df[datetime_col] <= reference_time)]
 
    return (
        recent.groupby("location_id")[count_col]
        .sum()
        .reset_index()
        .rename(columns={count_col: "current_count"})
    )
 

# Compare current count to threshold
# If missing falls back to historical average 
def classify_current_conditions(
    thresholds: pd.DataFrame,
    current_readings: pd.DataFrame,
    hourly_history: pd.DataFrame,
    count_col: str = "total_count",
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
 
    return merged[["location_id", "reading_used", "threshold", "level", "used_fallback"]]


# ------------------------------------------------------------
# Shortcut: fetch + score
# ------------------------------------------------------------
def get_scores(location_id=None, database_url: str = None) -> pd.DataFrame:

    hourly_history = fetch_hourly_history(location_id, database_url)
    live_minutes = fetch_recent_minutes(location_id, database_url=database_url)
 
    thresholds = calculate_thresholds(hourly_history)
    current_readings = get_last_hour_total(live_minutes)
    return classify_current_conditions(thresholds, current_readings, hourly_history)

