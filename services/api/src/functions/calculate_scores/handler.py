# Lambda entry point: GET /crowd-rating?sensor_id=xx
# Returns current High/Low crowd rating of the specific sensor
# Reads from Postgres and calculates the score using get_scores() from scoring_logic.py (same folder).


# PENDING -- not sure yet how this fits api-contract.md
#   -> The contract only shows GET /congestion. It has no sensor_id,
#      and returns ALL sensors as a list, wrapped in {"success", "data"}.
#      This handler is still one sensor only. 
#      Need to check if this should become /congestion, or stay separate.



import json
import pandas as pd

from src.functions.calculate_scores.scoring_logic import get_scores, fetch_sensor_details
 

# Reads sensor_id, calls get_scores(), and returns one sensor's result as JSON. 
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
 
    details = fetch_sensor_details(sensor_id)
    name, latitude, longitude = None, None, None
    if not details.empty:
        detail_row = details.iloc[0]
        name = detail_row["sensor_description"]
        latitude = float(detail_row["latitude"]) if pd.notna(detail_row["latitude"]) else None
        longitude = float(detail_row["longitude"]) if pd.notna(detail_row["longitude"]) else None
 
    body = {
            "success": True,
            "data": {
                "id": str(row["location_id"]),
                "name": name,
                "coordinates": {"latitude": latitude, "longitude": longitude},
                "indicator": row["level"].upper(),
                "pedestrianCount": int(round(row["reading_used"])),

                # sensory_level/refuge_nearby/threshold are NOT in api-contract.md's documented GET /congestion example
                # kept for now, pending confirmation
                "sensory_level": row["sensory_level"].upper(),
                "refuge_nearby": bool(row["refuge_nearby"]),
                "threshold": float(row["threshold"]),

                "freshness": {
                    "observedAt": _isoformat_or_none(row["observed_at"]),
                    "stale": bool(row["used_fallback"]),
                    "fallbackUsed": bool(row["used_fallback"]),
                },
            },
        }
    return _response(200, body)


# Gets sensor_id from the query string, or raises if it's missing/invalid. 
def _get_sensor_id(event) -> int:
    params = event.get("queryStringParameters") or {}
    raw_id = params.get("sensor_id")
    if raw_id is None:
        raise KeyError("Missing required query parameter: sensor_id")
    try:
        return int(raw_id)
    except ValueError:
        raise ValueError(f"sensor_id must be an integer, got: {raw_id}")
 

# Wraps a status code and body into the shape API Gateway expects. 
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


# Builds an error response matching api-contract.md's failure envelope.
def _error_response(status_code: int, code: str, message: str) -> dict:
    return _response(status_code, {
        "success": False,
        "error": {"code": code, "message": message},
    })