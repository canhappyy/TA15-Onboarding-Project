-- ClearWay database schema
-- Built directly from the confirmed ERD. Do not restructure without
-- re-running the normalization walkthrough this was checked against.
--
-- Naming standardized to PEDESTRIAN_HOURLY_COUNT (matches ERD/diagrams).
-- The unit template's "PEDESTRIAN_HOUR_COUNT" spelling is deprecated —
-- update the template doc to match this, not the other way round.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Sensor metadata (occasional updates) -> US1.1, US1.2
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS SENSOR_LOCATION (
    Location_ID         INTEGER PRIMARY KEY,
    Sensor_Description  TEXT,
    Sensor_Name         TEXT,
    Installation_Date   DATE,
    Note                TEXT,
    Location_Type       TEXT,      -- Indoor / Outdoor
    Status               TEXT,      -- 'A' = Active, etc.
    Direction_1_Label    TEXT,
    Direction_2_Label    TEXT,
    Latitude             REAL,
    Longitude            REAL
);

-- ---------------------------------------------------------------------
-- Pedestrian counts, hourly (daily batch updates) -> US1.1
-- One row per sensor per hour. Composite key per ERD:
-- (Location_ID, Sensing_DateTime).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS PEDESTRIAN_HOURLY_COUNT (
    Location_ID       INTEGER NOT NULL REFERENCES SENSOR_LOCATION(Location_ID),
    Sensing_DateTime  TEXT    NOT NULL,   -- ISO-8601, derived from Sensing_Date + HourDay
    Direction_1_Count INTEGER,
    Direction_2_Count INTEGER,
    Total_Count       INTEGER NOT NULL,
    Is_Imputed        INTEGER NOT NULL DEFAULT 0,  -- 1 if zero-filled for a gap
    PRIMARY KEY (Location_ID, Sensing_DateTime)
);

CREATE INDEX IF NOT EXISTS idx_hourly_datetime
    ON PEDESTRIAN_HOURLY_COUNT (Sensing_DateTime);

-- ---------------------------------------------------------------------
-- Pedestrian counts, minute-level / near-real-time (~15 min updates) -> US1.2
-- Composite key per ERD: (Sensing_DateTime, Location_ID).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS PEDESTRIAN_MINUTE_COUNT (
    Sensing_DateTime  TEXT    NOT NULL,
    Location_ID       INTEGER NOT NULL REFERENCES SENSOR_LOCATION(Location_ID),
    Direction_1_Count INTEGER,
    Direction_2_Count INTEGER,
    Total_Count       INTEGER NOT NULL,
    Is_Imputed        INTEGER NOT NULL DEFAULT 0,  -- 1 if zero-filled (no reading = 0, not missing)
    PRIMARY KEY (Sensing_DateTime, Location_ID)
);

CREATE INDEX IF NOT EXISTS idx_minute_datetime
    ON PEDESTRIAN_MINUTE_COUNT (Sensing_DateTime);

-- ---------------------------------------------------------------------
-- Landmarks, three-tier Theme -> Category -> Landmark (occasional
-- updates) -> US2.1. Split fixes the transitive dependency
-- (Category_id -> Theme -> Sub_Theme) found in the template's
-- normalization example.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS THEME (
    Theme_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    Theme      TEXT NOT NULL,
    Sub_Theme  TEXT NOT NULL,
    UNIQUE (Theme, Sub_Theme)
);

CREATE TABLE IF NOT EXISTS LANDMARK_CATEGORY (
    Category_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    Theme_id        INTEGER NOT NULL REFERENCES THEME(Theme_id),
    Category_Name   TEXT NOT NULL,   -- user-facing filter label
    Is_Refuge       INTEGER NOT NULL DEFAULT 0  -- explicit US2.1 allow-list flag
);

CREATE TABLE IF NOT EXISTS LANDMARK (
    Landmark_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    Category_id   INTEGER NOT NULL REFERENCES LANDMARK_CATEGORY(Category_id),
    Feature_Name  TEXT NOT NULL,
    Latitude      REAL,
    Longitude     REAL
);

CREATE INDEX IF NOT EXISTS idx_landmark_category ON LANDMARK (Category_id);
CREATE INDEX IF NOT EXISTS idx_category_refuge ON LANDMARK_CATEGORY (Is_Refuge);