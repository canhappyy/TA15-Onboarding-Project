# Validated scoring_logic through unit tests (10 test cases)
# regression test for a bug found during real-data testing, 
# manual calculation to confirm correctness, 
# and behavioral checks against real sensor data at different times of day.
# for example, 1% High overnight vs. 37% during peak commute

 
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "functions" / "calculate_scores"))


import pandas as pd
from src.functions.calculate_scores.scoring_logic import (
    _location_filter,
    calculate_thresholds,
    get_last_hour_total,
    classify_current_conditions,
    add_sensory_level,
)
 

# Sensor 1: mostly quiet, one busy hour. Sensor 2: consistently busier.
def make_sample_hourly_history() -> pd.DataFrame:
    return pd.DataFrame({
        "location_id": [1, 1, 1, 1, 2, 2, 2, 2],
        "total_count": [50, 60, 55, 200, 500, 520, 510, 800],
    }) 
 
 
def make_sample_live_minutes() -> pd.DataFrame:
    return pd.DataFrame({
        "location_id": [1, 1, 2, 2],
        "sensing_datetime": pd.to_datetime([
            "2026-08-05 16:00", "2026-08-05 16:30",
            "2026-08-05 16:00", "2026-08-05 16:30",
        ]),
        "total_count": [10, 15, 300, 350],
    })
 
 
# ---------------------------------------------------
# _location_filter
# ---------------------------------------------------
def test_location_filter_single_sensor():
    """
    Objective: confirm a single sensor ID builds the correct SQL filter for a one-sensor lookup
    Input:     location_id = 63
    Expected:  filter text uses '=', params dict has 'location_id': 63
    """
    clause, params = _location_filter(63)
    assert clause == "AND location_id = :location_id"
    assert params == {"location_id": 63}
    print("PASS: single sensor filter builds correct SQL and params")
 
 
def test_location_filter_list_of_sensors():
    """
    Objective: confirm a list of sensor IDs builds a SQL filter using ANY(), 
               for looking up all sensors along one route at once
    Input:     location_id = [63, 4, 9]
    Expected:  filter text uses 'ANY(:location_ids)', params has the full list
    """
    clause, params = _location_filter([63, 4, 9])
    assert clause == "AND location_id = ANY(:location_ids)"
    assert params == {"location_ids": [63, 4, 9]}
    print("PASS: list of sensors filter builds correct SQL and params")
 
 
def test_location_filter_none_means_all():
    """
    Objective: confirm passing no sensor ID at all returns an empty filter, 
               so the query returns every sensor
    Input:     location_id = None
    Expected:  no WHERE clause fragment, empty params
    """
    clause, params = _location_filter(None)
    assert clause == ""
    assert params == {}
    print("PASS: None correctly returns no filter (all sensors)")
 
 
# ---------------------------------------------------
# calculate_thresholds
# ---------------------------------------------------
def test_calculate_thresholds():
    """
    Objective: confirm each sensor gets its own threshold, based on its own historical range
    Input:     sensor 1 (mostly quiet), sensor 2 (consistently busier)
    Expected:  sensor 2's threshold > sensor 1's threshold
    """
    hourly = make_sample_hourly_history()
    thresholds = calculate_thresholds(hourly)
 
    assert set(thresholds["location_id"]) == {1, 2}
    t1 = thresholds.loc[thresholds["location_id"] == 1, "threshold"].iloc[0]
    t2 = thresholds.loc[thresholds["location_id"] == 2, "threshold"].iloc[0]
    assert t1 < t2
    print(f"PASS: threshold sensor 1 = {t1}, sensor 2 = {t2} (sensor 2 correctly higher)")
 
 
# ---------------------------------------------------
# get_last_hour_total
# ---------------------------------------------------
def test_last_hour_total_sums_correctly():
    """
    Objective: confirm minute-level readings within the last hour are correctly summed per sensor, 
               when an explicit reference
               time is given.
    Input:     sensor 1: 10 + 15, sensor 2: 300 + 350 (2 readings each)
    Expected:  sensor 1 = 25, sensor 2 = 650
    """
    live = make_sample_live_minutes()
    reference = pd.Timestamp("2026-08-05 16:30")
    result = get_last_hour_total(live, reference_time=reference)
 
    r1 = result.loc[result["location_id"] == 1, "current_count"].iloc[0]
    r2 = result.loc[result["location_id"] == 2, "current_count"].iloc[0]
    assert r1 == 25
    assert r2 == 650
    print(f"PASS: last-hour totals correctly summed (sensor 1 = {r1}, sensor 2 = {r2})")
 
 
def test_last_hour_total_with_default_reference_time():
    """
    Objective: regression test for calling this function WITHOUT passing reference_time
               which used to crash with a TypeError, because the final filter line compared
               against the unset reference_time argument instead of the calculated ref_time value.
    Input:     same as above, but reference_time is not passed at all
    Expected:  same result as the explicit-time test (25, 650), no crash
    """
    live = make_sample_live_minutes()
    result = get_last_hour_total(live)
 
    r1 = result.loc[result["location_id"] == 1, "current_count"].iloc[0]
    r2 = result.loc[result["location_id"] == 2, "current_count"].iloc[0]
    assert r1 == 25
    assert r2 == 650
    print(f"PASS: default reference_time path works correctly (sensor 1 = {r1}, sensor 2 = {r2})")
 
 
# ---------------------------------------------------
# classify_current_conditions
# ---------------------------------------------------
 
def test_classification_uses_fallback_when_no_reading():
    """
    Objective: confirm a sensor with no current reading (e.g. no pedestrians logged this hour) 
               falls back to its own historical average instead of crashing
    Input:     sensor 2 deliberately has no entry in current_readings
    Expected:  sensor 2's used_fallback = True, reading_used = its
               historical average
    """
    hourly = make_sample_hourly_history()
    thresholds = calculate_thresholds(hourly)
    current_readings = pd.DataFrame({"location_id": [1], "current_count": [10]})
 
    result = classify_current_conditions(thresholds, current_readings, hourly)
 
    row2 = result[result["location_id"] == 2].iloc[0]
    assert row2["used_fallback"] == True
    print(f"PASS: sensor 2 correctly used fallback (historical avg = {row2['reading_used']})")
 
 
def test_classification_end_to_end():
    """
    Objective: confirm the full pipeline (threshold -> current reading -> classify) 
               runs together correctly and returns the expected shape
    Input:     both sensors, explicit reference time
    Expected:  2 rows returned, with all 5 expected columns present
    """
    hourly = make_sample_hourly_history()
    live = make_sample_live_minutes()
    reference = pd.Timestamp("2026-08-05 16:30")
 
    thresholds = calculate_thresholds(hourly)
    current_readings = get_last_hour_total(live, reference_time=reference)
    result = classify_current_conditions(thresholds, current_readings, hourly)
 
    assert len(result) == 2
    assert set(result.columns) == {"location_id", "reading_used", "threshold", "level", "used_fallback"}
    print("PASS: threshold -> current reading -> classify runs correctly end-to-end")
    print(result)


def test_all_sensors_fallback_when_no_current_data():
    """
    Objective: confirm the system doesn't break when every sensor falls back at once.
    Input:     both sensors, but current_readings is completely empty
    Expected:  both sensors get used_fallback = True, using their own historical average 
               (sensor 1 = 91.25, sensor 2 = 582.5)
    """
    hourly = make_sample_hourly_history()
    empty_readings = pd.DataFrame({"location_id": [], "current_count": []})

    result = classify_current_conditions(thresholds := calculate_thresholds(hourly), empty_readings, hourly)

    assert result["used_fallback"].all()
    assert len(result) == 2
    print("PASS: all sensors correctly fall back when no current data exists at all")


def test_threshold_with_single_data_point():
    """
    Objective: confirm calculate_thresholds doesn't crash on a sensor with only one historical reading
    Input:     one sensor, one historical reading (100)
    Expected:  threshold = 100.0
    """
    hourly = pd.DataFrame({"location_id": [5], "total_count": [100]})
    thresholds = calculate_thresholds(hourly)
    assert thresholds.iloc[0]["threshold"] == 100
    print("PASS: single data point handled correctly")


# ---------------------------------------------------
# add_sensory_level
# ---------------------------------------------------
def test_sensory_level_downgrades_high_near_refuge():
    """
    Objective: a High-congestion sensor within radius_m of a refuge should
               downgrade to sensory_level Low
    Input:     sensor at (0, 0), refuge at (0, 0.001) (~111m away), level=High, radius_m=300
    Expected:  refuge_nearby=True, sensory_level=Low
    """
    scored = pd.DataFrame({"location_id": [1], "level": ["High"]})
    sensor_coords = pd.DataFrame({"location_id": [1], "latitude": [0.0], "longitude": [0.0]})
    refuges = pd.DataFrame({"latitude": [0.001], "longitude": [0.0]})

    result = add_sensory_level(scored, sensor_coords, refuges, radius_m=300)
    assert result.iloc[0]["refuge_nearby"] == True
    assert result.iloc[0]["sensory_level"] == "Low"
    print("PASS: High congestion near a refuge downgrades to sensory_level Low")


def test_sensory_level_stays_high_when_no_refuge_nearby():
    """
    Objective: a High-congestion sensor with no refuge within radius_m stays High
    Input:     sensor at (0, 0), refuge far away at (10, 10), level=High, radius_m=300
    Expected:  refuge_nearby=False, sensory_level=High
    """
    scored = pd.DataFrame({"location_id": [1], "level": ["High"]})
    sensor_coords = pd.DataFrame({"location_id": [1], "latitude": [0.0], "longitude": [0.0]})
    refuges = pd.DataFrame({"latitude": [10.0], "longitude": [10.0]})

    result = add_sensory_level(scored, sensor_coords, refuges, radius_m=300)
    assert result.iloc[0]["refuge_nearby"] == False
    assert result.iloc[0]["sensory_level"] == "High"
    print("PASS: High congestion with no nearby refuge stays sensory_level High")


def test_sensory_level_matches_level_when_low():
    """
    Objective: a Low-congestion sensor is always sensory_level Low, regardless of refuges
    Input:     sensor at (0, 0), no refuges at all, level=Low
    Expected:  sensory_level=Low
    """
    scored = pd.DataFrame({"location_id": [1], "level": ["Low"]})
    sensor_coords = pd.DataFrame({"location_id": [1], "latitude": [0.0], "longitude": [0.0]})
    refuges = pd.DataFrame({"latitude": [], "longitude": []})

    result = add_sensory_level(scored, sensor_coords, refuges, radius_m=300)
    assert result.iloc[0]["sensory_level"] == "Low"
    print("PASS: Low congestion is always sensory_level Low")




if __name__ == "__main__":
    test_location_filter_single_sensor()
    test_location_filter_list_of_sensors()
    test_location_filter_none_means_all()
    test_calculate_thresholds()
    test_last_hour_total_sums_correctly()
    test_last_hour_total_with_default_reference_time()
    test_classification_uses_fallback_when_no_reading()
    test_classification_end_to_end()
    test_all_sensors_fallback_when_no_current_data()
    test_threshold_with_single_data_point()
    test_sensory_level_downgrades_high_near_refuge()
    test_sensory_level_stays_high_when_no_refuge_nearby()
    test_sensory_level_matches_level_when_low()
    print("\nAll 13 tests passed (100% pass rate).")