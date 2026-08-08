"""Read-only PostgreSQL queries for route, refuge, and congestion services."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from typing import Any


REFUGE_SUBTHEMES: dict[str, frozenset[str]] = {
    "LIBRARY": frozenset({"library"}),
    "MUSEUM": frozenset({"museum"}),
    "GARDEN": frozenset({"garden", "public garden"}),
    "PARK": frozenset(
        {
            "park",
            "public park",
            "informal outdoor facility (park/garden/reserve)",
        }
    ),
}
SUBTHEME_TO_CATEGORY = {
    subtheme: category
    for category, subthemes in REFUGE_SUBTHEMES.items()
    for subtheme in subthemes
}


@dataclass(frozen=True)
class BoundingBox:
    south: float
    west: float
    north: float
    east: float

    def __post_init__(self) -> None:
        if not -90 <= self.south <= 90 or not -90 <= self.north <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= self.west <= 180 or not -180 <= self.east <= 180:
            raise ValueError("longitude must be between -180 and 180")
        if self.south > self.north:
            raise ValueError("south must not exceed north")
        if self.west > self.east:
            raise ValueError("west must not exceed east")


@dataclass(frozen=True)
class SensorCondition:
    location_id: int
    name: str
    latitude: float
    longitude: float
    live_60_minute_total: int | None
    latest_observed_at: datetime | None
    historical_hourly_mean: float | None
    historical_hourly_p75: float | None


@dataclass(frozen=True)
class RefugeRecord:
    landmark_id: int
    name: str
    category: str
    theme: str
    sub_theme: str
    latitude: float
    longitude: float


class PostgresApiRepository:
    """Read application data using a caller-owned psycopg connection."""

    def __init__(self, connection: Any):
        self._connection = connection

    def list_sensor_conditions(
        self,
        reference_time: datetime,
        bounds: BoundingBox | None = None,
    ) -> list[SensorCondition]:
        self._require_aware_datetime(reference_time)
        bounds_sql, parameters = self._bounds_filter(bounds, alias="sensor")
        parameters["reference_time"] = reference_time
        statement = f"""
            WITH eligible_sensors AS (
                SELECT sensor.location_id,
                    COALESCE(
                        NULLIF(BTRIM(sensor.sensor_name), ''),
                        NULLIF(BTRIM(sensor.sensor_description), ''),
                        'Sensor ' || sensor.location_id::text
                    ) AS name,
                    sensor.latitude,
                    sensor.longitude
                FROM sensor_location AS sensor
                WHERE sensor.status = 'A'
                    AND sensor.latitude IS NOT NULL
                    AND sensor.longitude IS NOT NULL
                    {bounds_sql}
            ),
            live_counts AS (
                SELECT minute.location_id,
                    SUM(minute.total_count)::bigint AS live_total
                FROM pedestrian_minute_count AS minute
                JOIN eligible_sensors AS sensor
                    ON sensor.location_id = minute.location_id
                WHERE minute.is_imputed = FALSE
                    AND minute.sensing_datetime
                        > %(reference_time)s - INTERVAL '60 minutes'
                    AND minute.sensing_datetime <= %(reference_time)s
                GROUP BY minute.location_id
            ),
            latest_observations AS (
                SELECT minute.location_id,
                    MAX(minute.sensing_datetime) AS latest_observed_at
                FROM pedestrian_minute_count AS minute
                JOIN eligible_sensors AS sensor
                    ON sensor.location_id = minute.location_id
                WHERE minute.is_imputed = FALSE
                    AND minute.sensing_datetime <= %(reference_time)s
                GROUP BY minute.location_id
            ),
            hourly_baselines AS (
                SELECT hourly.location_id,
                    AVG(hourly.total_count)::double precision AS hourly_mean,
                    percentile_cont(0.75) WITHIN GROUP (
                        ORDER BY hourly.total_count
                    )::double precision AS hourly_p75
                FROM pedestrian_hourly_count AS hourly
                JOIN eligible_sensors AS sensor
                    ON sensor.location_id = hourly.location_id
                WHERE hourly.is_imputed = FALSE
                    AND hourly.sensing_datetime
                        > %(reference_time)s - INTERVAL '90 days'
                    AND hourly.sensing_datetime <= %(reference_time)s
                GROUP BY hourly.location_id
            )
            SELECT sensor.location_id, sensor.name, sensor.latitude,
                sensor.longitude, live.live_total,
                latest.latest_observed_at, baseline.hourly_mean,
                baseline.hourly_p75
            FROM eligible_sensors AS sensor
            LEFT JOIN live_counts AS live
                ON live.location_id = sensor.location_id
            LEFT JOIN latest_observations AS latest
                ON latest.location_id = sensor.location_id
            LEFT JOIN hourly_baselines AS baseline
                ON baseline.location_id = sensor.location_id
            ORDER BY sensor.location_id
        """
        with self._connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            rows = cursor.fetchall()
        conditions = [
            SensorCondition(
                location_id=row[0],
                name=row[1],
                latitude=row[2],
                longitude=row[3],
                live_60_minute_total=row[4],
                latest_observed_at=row[5],
                historical_hourly_mean=(
                    float(row[6]) if row[6] is not None else None
                ),
                historical_hourly_p75=(
                    float(row[7]) if row[7] is not None else None
                ),
            )
            for row in rows
        ]
        return sorted(conditions, key=lambda condition: condition.location_id)

    def get_latest_minute_timestamp(self) -> datetime | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT MAX(sensing_datetime)
                FROM pedestrian_minute_count AS minute
                JOIN sensor_location AS sensor
                    ON sensor.location_id = minute.location_id
                WHERE minute.is_imputed = FALSE
                    AND sensor.status = 'A'
                    AND sensor.latitude IS NOT NULL
                    AND sensor.longitude IS NOT NULL
                """
            )
            row = cursor.fetchone()
        return row[0] if row else None

    def list_refuges(
        self,
        bounds: BoundingBox | None = None,
        categories: Collection[str] | None = None,
    ) -> list[RefugeRecord]:
        selected_categories = self._normalize_categories(categories)
        if not selected_categories:
            return []

        subthemes = sorted(
            {
                subtheme
                for category in selected_categories
                for subtheme in REFUGE_SUBTHEMES[category]
            }
        )
        bounds_sql, parameters = self._bounds_filter(bounds, alias="landmark")
        parameters["subthemes"] = subthemes
        statement = f"""
            SELECT landmark.landmark_id, landmark.feature_name,
                stored_theme.theme, stored_theme.sub_theme,
                landmark.latitude, landmark.longitude
            FROM landmark
            JOIN landmark_category AS category
                ON category.category_id = landmark.category_id
            JOIN theme AS stored_theme
                ON stored_theme.theme_id = category.theme_id
            WHERE category.is_refuge = TRUE
                AND landmark.latitude IS NOT NULL
                AND landmark.longitude IS NOT NULL
                AND LOWER(BTRIM(stored_theme.sub_theme))
                    = ANY(%(subthemes)s)
                {bounds_sql}
            ORDER BY landmark.landmark_id
        """
        with self._connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            rows = cursor.fetchall()

        refuges = []
        for row in rows:
            category = SUBTHEME_TO_CATEGORY.get(row[3].strip().casefold())
            if category not in selected_categories:
                continue
            refuges.append(
                RefugeRecord(
                    landmark_id=row[0],
                    name=row[1],
                    category=category,
                    theme=row[2],
                    sub_theme=row[3],
                    latitude=row[4],
                    longitude=row[5],
                )
            )
        return sorted(
            refuges,
            key=lambda refuge: (refuge.category, refuge.name, refuge.landmark_id),
        )

    @staticmethod
    def _require_aware_datetime(value: datetime) -> None:
        if value.utcoffset() is None:
            raise ValueError("reference_time must be timezone-aware")

    @staticmethod
    def _bounds_filter(
        bounds: BoundingBox | None,
        *,
        alias: str,
    ) -> tuple[str, dict[str, Any]]:
        if bounds is None:
            return "", {}
        return (
            f"""
                AND {alias}.latitude BETWEEN %(south)s AND %(north)s
                AND {alias}.longitude BETWEEN %(west)s AND %(east)s
            """,
            {
                "south": bounds.south,
                "west": bounds.west,
                "north": bounds.north,
                "east": bounds.east,
            },
        )

    @staticmethod
    def _normalize_categories(
        categories: Collection[str] | None,
    ) -> frozenset[str]:
        if categories is None:
            return frozenset(REFUGE_SUBTHEMES)
        values = [categories] if isinstance(categories, str) else categories
        normalized = frozenset(value.strip().upper() for value in values)
        unsupported = sorted(normalized - REFUGE_SUBTHEMES.keys())
        if unsupported:
            raise ValueError(
                f"Unsupported refuge category: {', '.join(unsupported)}"
            )
        return normalized
