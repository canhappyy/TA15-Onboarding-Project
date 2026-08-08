"""Reusable pandas transformations shared by local and Lambda ingestion."""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd


MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
COORDINATES_PATTERN = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$"
)
REFUGE_CATEGORIES = {
    "library": "LIBRARY",
    "museum": "MUSEUM",
    "garden": "GARDEN",
    "public garden": "GARDEN",
    "park": "PARK",
    "public park": "PARK",
    "informal outdoor facility (park/garden/reserve)": "PARK",
}


def transform_sensors(frame: pd.DataFrame) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    positions: dict[int, int] = {}
    rejected: list[dict[str, Any]] = []
    duplicates = 0

    for index, row in frame.iterrows():
        raw_location_id = _value(row, "Location_ID", "location_id")
        if _is_blank(raw_location_id):
            rejected.append(_rejection(index, "MISSING_LOCATION_ID"))
            continue
        try:
            location_id = _integer(raw_location_id)
        except (TypeError, ValueError):
            rejected.append(_rejection(index, "INVALID_LOCATION_ID"))
            continue

        record = {
            "location_id": location_id,
            "sensor_description": _text(
                _value(row, "Sensor_Description", "sensor_description")
            ),
            "sensor_name": _text(_value(row, "Sensor_Name", "sensor_name")),
            "installation_date": _date_or_none(
                _value(row, "Installation_Date", "installation_date")
            ),
            "note": _text(_value(row, "Note", "note")),
            "location_type": _text(_value(row, "Location_Type", "location_type")),
            "status": _text(_value(row, "Status", "status")),
            "direction_1_label": _text(
                _value(row, "Direction_1", "direction_1_label")
            ),
            "direction_2_label": _text(
                _value(row, "Direction_2", "direction_2_label")
            ),
            "latitude": _float_or_none(_value(row, "Latitude", "latitude")),
            "longitude": _float_or_none(_value(row, "Longitude", "longitude")),
        }
        if location_id in positions:
            duplicates += 1
            records[positions[location_id]] = record
        else:
            positions[location_id] = len(records)
            records.append(record)

    return _result(records, rejected, duplicates)


def transform_minute_counts(frame: pd.DataFrame) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    positions: dict[tuple[int, str], int] = {}
    rejected: list[dict[str, Any]] = []
    duplicates = 0

    for index, row in frame.iterrows():
        try:
            location_id = _required_location_id(row)
            sensing_datetime = _minute_datetime(row)
            total_count = _required_count(
                _value(
                    row,
                    "Total_of_Directions",
                    "total_of_directions",
                    "total_count",
                )
            )
            direction_1 = _optional_count(
                _value(row, "Direction_1", "direction_1", "direction_1_count")
            )
            direction_2 = _optional_count(
                _value(row, "Direction_2", "direction_2", "direction_2_count")
            )
        except TransformError as error:
            rejected.append(_rejection(index, error.code))
            continue

        record = {
            "location_id": location_id,
            "sensing_datetime": sensing_datetime,
            "direction_1_count": direction_1,
            "direction_2_count": direction_2,
            "total_count": total_count,
            "is_imputed": False,
        }
        key = (location_id, sensing_datetime)
        if key in positions:
            duplicates += 1
            records[positions[key]] = record
        else:
            positions[key] = len(records)
            records.append(record)

    return _result(records, rejected, duplicates)


def transform_hourly_counts(frame: pd.DataFrame) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    keys: set[tuple[int, str]] = set()
    rejected: list[dict[str, Any]] = []
    duplicates = 0

    for index, row in frame.iterrows():
        try:
            location_id = _required_location_id(row)
            sensing_datetime = _hourly_datetime(row)
            total_count = _required_count(
                _value(
                    row,
                    "Total_of_Directions",
                    "total_of_directions",
                    "total_count",
                    "pedestriancount",
                )
            )
            direction_1 = _optional_count(
                _value(row, "Direction_1", "direction_1", "direction_1_count")
            )
            direction_2 = _optional_count(
                _value(row, "Direction_2", "direction_2", "direction_2_count")
            )
        except TransformError as error:
            rejected.append(_rejection(index, error.code))
            continue

        key = (location_id, sensing_datetime)
        if key in keys:
            duplicates += 1
            continue
        keys.add(key)
        records.append(
            {
                "location_id": location_id,
                "sensing_datetime": sensing_datetime,
                "direction_1_count": direction_1,
                "direction_2_count": direction_2,
                "total_count": total_count,
                "is_imputed": False,
            }
        )

    return _result(records, rejected, duplicates)


def transform_landmarks(frame: pd.DataFrame) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for index, row in frame.iterrows():
        theme = _text(_value(row, "Theme", "theme"))
        sub_theme = _text(_value(row, "Sub Theme", "Sub_Theme", "sub_theme"))
        feature_name = _text(
            _value(row, "Feature Name", "Feature_Name", "feature_name")
        )
        if theme is None:
            rejected.append(_rejection(index, "MISSING_THEME"))
            continue
        if sub_theme is None:
            rejected.append(_rejection(index, "MISSING_SUB_THEME"))
            continue
        if feature_name is None:
            rejected.append(_rejection(index, "MISSING_FEATURE_NAME"))
            continue

        latitude, longitude = _coordinates(row)
        records.append(
            {
                "theme": theme,
                "sub_theme": sub_theme,
                "feature_name": feature_name,
                "latitude": latitude,
                "longitude": longitude,
                "refuge_category": _refuge_category(sub_theme),
            }
        )

    return _result(records, rejected, duplicates_resolved=0)


class TransformError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _result(
    records: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    duplicates_resolved: int,
) -> dict[str, Any]:
    return {
        "records": records,
        "rejected": rejected,
        "rejected_count": len(rejected),
        "duplicates_resolved": duplicates_resolved,
    }


def _rejection(index: Any, code: str) -> dict[str, Any]:
    return {"index": int(index), "code": code}


def _value(row: pd.Series, *keys: str) -> Any:
    for key in keys:
        if key in row.index:
            return row[key]
    return None


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _text(value: Any) -> str | None:
    return None if _is_blank(value) else str(value).strip()


def _integer(value: Any) -> int:
    if isinstance(value, bool) or _is_blank(value):
        raise ValueError
    number = float(str(value).strip())
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError
    return int(number)


def _required_location_id(row: pd.Series) -> int:
    value = _value(row, "Location_ID", "location_id")
    if _is_blank(value):
        raise TransformError("MISSING_LOCATION_ID")
    try:
        return _integer(value)
    except (TypeError, ValueError) as error:
        raise TransformError("INVALID_LOCATION_ID") from error


def _required_count(value: Any) -> int:
    if _is_blank(value):
        raise TransformError("MISSING_TOTAL_COUNT")
    try:
        count = _integer(value)
    except (TypeError, ValueError) as error:
        raise TransformError("INVALID_TOTAL_COUNT") from error
    if count < 0:
        raise TransformError("INVALID_TOTAL_COUNT")
    return count


def _optional_count(value: Any) -> int | None:
    if _is_blank(value):
        return None
    try:
        count = _integer(value)
    except (TypeError, ValueError) as error:
        raise TransformError("INVALID_DIRECTION_COUNT") from error
    if count < 0:
        raise TransformError("INVALID_DIRECTION_COUNT")
    return count


def _date_or_none(value: Any) -> str | None:
    if _is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.date().isoformat()


def _float_or_none(value: Any) -> float | None:
    if _is_blank(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _minute_datetime(row: pd.Series) -> str:
    sensing_date = _value(row, "sensing_date", "Sensing_Date")
    sensing_time = _value(row, "sensing_time", "Sensing_Time")
    if not _is_blank(sensing_date) and not _is_blank(sensing_time):
        try:
            naive = pd.Timestamp(f"{str(sensing_date).strip()} {str(sensing_time).strip()}")
            return naive.tz_localize(
                MELBOURNE_TZ, ambiguous=True, nonexistent="shift_forward"
            ).isoformat()
        except (TypeError, ValueError) as error:
            raise TransformError("INVALID_TIMESTAMP") from error

    value = _value(row, "Sensing_DateTime", "sensing_datetime")
    if _is_blank(value):
        raise TransformError("MISSING_TIMESTAMP")
    try:
        parsed = pd.Timestamp(value)
        if parsed.tzinfo is None:
            parsed = parsed.tz_localize(
                MELBOURNE_TZ, ambiguous=True, nonexistent="shift_forward"
            )
        return parsed.isoformat()
    except (TypeError, ValueError) as error:
        raise TransformError("INVALID_TIMESTAMP") from error


def _hourly_datetime(row: pd.Series) -> str:
    raw_date = _value(row, "Sensing_Date", "sensing_date")
    raw_hour = _value(row, "HourDay", "hourday", "hour_day")
    if _is_blank(raw_date) or _is_blank(raw_hour):
        raise TransformError("MISSING_TIMESTAMP")
    try:
        hour = _integer(raw_hour)
        if hour < 0 or hour > 23:
            raise ValueError
        naive = pd.Timestamp(f"{str(raw_date).strip()} {hour:02d}:00:00")
        return naive.tz_localize(
            MELBOURNE_TZ, ambiguous=True, nonexistent="shift_forward"
        ).isoformat()
    except (TypeError, ValueError) as error:
        raise TransformError("INVALID_TIMESTAMP") from error


def _coordinates(row: pd.Series) -> tuple[float | None, float | None]:
    value = _value(row, "Co-ordinates", "co_ordinates", "coordinates")
    if isinstance(value, str):
        match = COORDINATES_PATTERN.match(value)
        return (
            (float(match.group(1)), float(match.group(2)))
            if match
            else (None, None)
        )
    if isinstance(value, dict):
        return (
            _float_or_none(value.get("lat", value.get("latitude"))),
            _float_or_none(
                value.get("lon", value.get("lng", value.get("longitude")))
            ),
        )
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return _float_or_none(value[0]), _float_or_none(value[1])
    return (
        _float_or_none(_value(row, "Latitude", "latitude")),
        _float_or_none(_value(row, "Longitude", "longitude")),
    )


def _refuge_category(sub_theme: str) -> str | None:
    return REFUGE_CATEGORIES.get(sub_theme.casefold())
