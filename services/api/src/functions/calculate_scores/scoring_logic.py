# Gives each sensor a High or Low score, based on its own past data.
# Each sensor has its own threshold, not one fixed number for all.
 
import pandas as pd
import numpy as np
 
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