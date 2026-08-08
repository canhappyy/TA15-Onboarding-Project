"""Pure row normalization shared by bootstrap and scheduled ingestion."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo


MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
COORDINATES_PATTERN = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$"
)


def normalize_sensors(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records_by_id: dict[int, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    duplicates_resolved = 0

    for index, row in enumerate(rows):
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
        if location_id in records_by_id:
            duplicates_resolved += 1
        records_by_id[location_id] = record

    return _result(list(records_by_id.values()), rejected, duplicates_resolved)


def normalize_minute_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records_by_key: dict[tuple[int, str], dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    duplicates_resolved = 0

    for index, row in enumerate(rows):
        try:
            location_id = _required_location_id(row)
            sensing_datetime = _minute_datetime(row)
            total_count = _required_count(
                _value(row, "Total_of_Directions", "total_of_directions", "total_count")
            )
            direction_1 = _optional_count(
                _value(row, "Direction_1", "direction_1", "direction_1_count")
            )
            direction_2 = _optional_count(
                _value(row, "Direction_2", "direction_2", "direction_2_count")
            )
        except NormalizationError as error:
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
        if key in records_by_key:
            duplicates_resolved += 1
        records_by_key[key] = record

    return _result(list(records_by_key.values()), rejected, duplicates_resolved)


def normalize_hourly_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records_by_key: dict[tuple[int, str], dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    duplicates_resolved = 0

    for index, row in enumerate(rows):
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
        except NormalizationError as error:
            rejected.append(_rejection(index, error.code))
            continue

        key = (location_id, sensing_datetime)
        if key in records_by_key:
            duplicates_resolved += 1
            continue
        records_by_key[key] = {
            "location_id": location_id,
            "sensing_datetime": sensing_datetime,
            "direction_1_count": direction_1,
            "direction_2_count": direction_2,
            "total_count": total_count,
            "is_imputed": False,
        }

    return _result(list(records_by_key.values()), rejected, duplicates_resolved)


def normalize_landmarks(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
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
            }
        )

    return _result(records, rejected, duplicates_resolved=0)


class NormalizationError(ValueError):
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


def _rejection(index: int, code: str) -> dict[str, Any]:
    return {"index": index, "code": code}


def _value(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return isinstance(value, float) and math.isnan(value)


def _text(value: Any) -> str | None:
    if _is_blank(value):
        return None
    return str(value).strip()


def _integer(value: Any) -> int:
    if isinstance(value, bool) or _is_blank(value):
        raise ValueError
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError
        return int(value)
    return int(str(value).strip())


def _required_location_id(row: Mapping[str, Any]) -> int:
    value = _value(row, "Location_ID", "location_id")
    if _is_blank(value):
        raise NormalizationError("MISSING_LOCATION_ID")
    try:
        return _integer(value)
    except (TypeError, ValueError) as error:
        raise NormalizationError("INVALID_LOCATION_ID") from error


def _required_count(value: Any) -> int:
    if _is_blank(value):
        raise NormalizationError("MISSING_TOTAL_COUNT")
    try:
        count = _integer(value)
    except (TypeError, ValueError) as error:
        raise NormalizationError("INVALID_TOTAL_COUNT") from error
    if count < 0:
        raise NormalizationError("INVALID_TOTAL_COUNT")
    return count


def _optional_count(value: Any) -> int | None:
    if _is_blank(value):
        return None
    try:
        count = _integer(value)
    except (TypeError, ValueError) as error:
        raise NormalizationError("INVALID_DIRECTION_COUNT") from error
    if count < 0:
        raise NormalizationError("INVALID_DIRECTION_COUNT")
    return count


def _date_or_none(value: Any) -> str | None:
    if _is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        return None


def _float_or_none(value: Any) -> float | None:
    if _is_blank(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _minute_datetime(row: Mapping[str, Any]) -> str:
    sensing_date = _value(row, "sensing_date", "Sensing_Date")
    sensing_time = _value(row, "sensing_time", "Sensing_Time")
    if not _is_blank(sensing_date) and not _is_blank(sensing_time):
        try:
            naive = datetime.strptime(
                f"{str(sensing_date).strip()} {str(sensing_time).strip()}",
                "%Y-%m-%d %H:%M",
            )
        except ValueError as error:
            raise NormalizationError("INVALID_TIMESTAMP") from error
        return _localize_melbourne(naive).isoformat()

    value = _value(row, "Sensing_DateTime", "sensing_datetime")
    if _is_blank(value):
        raise NormalizationError("MISSING_TIMESTAMP")
    try:
        parsed = _parse_datetime(value)
    except (TypeError, ValueError) as error:
        raise NormalizationError("INVALID_TIMESTAMP") from error
    if parsed.tzinfo is None:
        parsed = _localize_melbourne(parsed)
    return parsed.isoformat()


def _hourly_datetime(row: Mapping[str, Any]) -> str:
    raw_date = _value(row, "Sensing_Date", "sensing_date")
    raw_hour = _value(row, "HourDay", "hourday", "hour_day")
    if _is_blank(raw_date) or _is_blank(raw_hour):
        raise NormalizationError("MISSING_TIMESTAMP")
    try:
        sensing_date = date.fromisoformat(str(raw_date).strip())
        hour = _integer(raw_hour)
        if hour < 0 or hour > 23:
            raise ValueError
    except (TypeError, ValueError) as error:
        raise NormalizationError("INVALID_TIMESTAMP") from error
    naive = datetime.combine(sensing_date, datetime.min.time()).replace(hour=hour)
    return _localize_melbourne(naive).isoformat()


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        for pattern in ("%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text, pattern)
            except ValueError:
                continue
    raise ValueError


def _localize_melbourne(naive: datetime) -> datetime:
    candidate = naive.replace(tzinfo=MELBOURNE_TZ, fold=0)
    normalized = candidate.astimezone(timezone.utc).astimezone(MELBOURNE_TZ)
    if normalized.replace(tzinfo=None) != naive:
        return normalized
    return candidate


def _coordinates(row: Mapping[str, Any]) -> tuple[float | None, float | None]:
    value = _value(row, "Co-ordinates", "co_ordinates", "coordinates")
    if isinstance(value, str):
        match = COORDINATES_PATTERN.match(value)
        if match:
            return float(match.group(1)), float(match.group(2))
        return None, None
    if isinstance(value, Mapping):
        return (
            _float_or_none(_value(value, "lat", "latitude")),
            _float_or_none(_value(value, "lon", "lng", "longitude")),
        )
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return _float_or_none(value[0]), _float_or_none(value[1])
    return (
        _float_or_none(_value(row, "Latitude", "latitude")),
        _float_or_none(_value(row, "Longitude", "longitude")),
    )
