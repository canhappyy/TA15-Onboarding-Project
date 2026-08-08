"""Adapt Open Data row dictionaries to reusable pandas transformations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Callable

import pandas as pd

from src.pipeline.transforms import (
    transform_hourly_counts,
    transform_landmarks,
    transform_minute_counts,
    transform_sensors,
)


def normalize_sensors(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return _transform(rows, transform_sensors)


def normalize_minute_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return _transform(rows, transform_minute_counts)


def normalize_hourly_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return _transform(rows, transform_hourly_counts)


def normalize_landmarks(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return _transform(rows, transform_landmarks)


def _transform(
    rows: Iterable[Mapping[str, Any]],
    transformer: Callable[[pd.DataFrame], dict[str, Any]],
) -> dict[str, Any]:
    return transformer(pd.DataFrame.from_records(list(rows)))
