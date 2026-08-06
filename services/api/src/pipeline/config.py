"""
ClearWay data pipeline configuration (PostgreSQL version).

Connection details come from a local .env file -- create one from
.env.example and never commit it (it's already covered by the repo's
.gitignore rule for .env*).

Everything else (refuge rules, score thresholds, source file paths) is
unchanged from the SQLite prototype.
"""
from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv()

# --------------------------------------------------------------------------
# Database connection
# --------------------------------------------------------------------------
PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = os.getenv("PGPORT", "5432")
PGDATABASE = os.getenv("PGDATABASE", "clearway")
PGUSER = os.getenv("PGUSER", "clearway")
PGPASSWORD = os.getenv("PGPASSWORD", "clearway_dev")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}",
)

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"

RAW_DIR = Path(os.getenv("RAW_DIR", BASE_DIR / "data"))
SENSOR_LOCATIONS_CSV = RAW_DIR / "pedestrian-counting-system-sensor-locations.csv"
HOURLY_COUNTS_CSV = RAW_DIR / "pedestrian-counting-system-monthly-counts-per-hour.csv"
MINUTE_COUNTS_CSV = RAW_DIR / "pedestrian-counting-system-past-hour-counts-per-minute.csv"
LANDMARKS_CSV = RAW_DIR / (
    "landmarks-and-places-of-interest-including-schools-theatres-health-services-spor.csv"
)

# --------------------------------------------------------------------------
# US2.1 -- Refuge category rules
# --------------------------------------------------------------------------
REFUGE_THEME_SUBTHEME_PAIRS = [
    ("Leisure/Recreation", "Informal Outdoor Facility (Park/Garden/Reserve)"),
]

CATEGORY_DISPLAY_NAMES = {
    "Informal Outdoor Facility (Park/Garden/Reserve)": "Park / Garden",
}

# --------------------------------------------------------------------------
# US1.1 / US1.2 -- Sensory score rules
# --------------------------------------------------------------------------
HIGH_DENSITY_THRESHOLD = 200
ACTIVE_SENSOR_STATUS = "A"
REALTIME_WINDOW_MINUTES = 30
