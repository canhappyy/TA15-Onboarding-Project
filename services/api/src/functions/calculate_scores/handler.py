# Lambda entry point: GET /crowd-rating?sensor_id=xx
# Returns current High/Low crowd rating of the specific sensor
# Reads from Postgres and calculates the score using get_scores() from scoring_logic.py (same folder).

 
import json
import pandas as pd

from src.functions.calculate_scores.scoring_logic import get_scores
 
 
def lambda_handler(event, context):
    try:
        sensor_id = _get_sensor_id(event)
    except (KeyError, ValueError) as e:
        return _error_response(400, "INVALID_REQUEST", str(e))
 
    results = get_scores(sensor_id)
 
    sensor_row = results[results["location_id"] == sensor_id]
    if sensor_row.empty:
        return _error_response(404, "NOT_FOUND", f"No data found for sensor_id {sensor_id}")
 
    row = sensor_row.iloc[0]
    body = {
        "sensor_id": int(row["location_id"]),
        "level": row["level"].upper(),
        "sensory_level": row["sensory_level"].upper(),
        "refuge_nearby": bool(row["refuge_nearby"]),
        "reading_used": float(row["reading_used"]),
        "threshold": float(row["threshold"]),
        "used_fallback": bool(row["used_fallback"]),
        "observed_at": _isoformat_or_none(row["observed_at"]),
    }
    return _response(200, body)
 
 
def _get_sensor_id(event) -> int:
    params = event.get("queryStringParameters") or {}
    raw_id = params.get("sensor_id")
    if raw_id is None:
        raise KeyError("Missing required query parameter: sensor_id")
    try:
        return int(raw_id)
    except ValueError:
        raise ValueError(f"sensor_id must be an integer, got: {raw_id}")
 
 
def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


# Converts a pandas Timestamp to an ISO string, or None if it's NaT/missing.
def _isoformat_or_none(value):
    if pd.isna(value):
        return None
    return value.isoformat()


def _error_response(status_code: int, code: str, message: str) -> dict:
    return _response(status_code, {
        "success": False,
        "error": {"code": code, "message": message},
    })