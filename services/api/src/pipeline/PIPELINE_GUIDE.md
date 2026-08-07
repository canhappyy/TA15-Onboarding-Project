# ClearWay Data Pipeline — Reference & Testing Guide

## What this is

Everything under `services/api/src/pipeline/` is responsible for one job:
take the raw Melbourne Open Data CSVs and load them into Postgres in a
clean, query-ready shape. It's step one of a longer chain:

```
schema.sql  →  pipeline scripts  →  Postgres  →  scoring_logic.py  →  API handler  →  frontend
(tables)       (fill tables)        (storage)     (reads + scores)    (not built yet)
```

Nothing downstream has real data to work with until the pipeline has run
at least once.

---

## The files, what each one does

| File | Job |
|---|---|
| `packages/database/schema.sql` | The blueprint — creates the 6 empty tables. **Canonical copy**, lives outside the pipeline folder. |
| `config.py` | Settings: DB connection (from `.env`), CSV file paths, refuge rules, thresholds. Nothing is hardcoded elsewhere. |
| `build_schema.py` | Runs `schema.sql` against Postgres. Run first, always. |
| `ingest_sensor_locations.py` | Loads sensor metadata (names, status, coordinates) → `sensor_location`. |
| `ingest_pedestrian_minute.py` | Loads near-real-time minute counts → `pedestrian_minute_count`. Fills gaps with zero (no reading = no pedestrians). |
| `ingest_pedestrian_hourly.py` | Loads historical hourly counts → `pedestrian_hourly_count`. Backfills stub sensor rows for any decommissioned sensor IDs found only in historical data. |
| `ingest_landmarks.py` | Loads landmarks → `theme` / `landmark_category` / `landmark`, tagging which categories count as sensory refuges. |
| `run_pipeline.py` | Runs everything above, in the correct order, in one command. |
| `.env` (not committed) | Your local DB credentials + CSV folder path. Copy from `.env.example`. |
| `data/` (not committed) | Where you put the 4 downloaded CSVs. Gitignored — real data never goes into GitHub. |

## Why the order matters

`sensor_location` must be loaded **before** either count table, because both
count tables have a foreign key pointing at `location_id` — Postgres will
reject a count row for a sensor that doesn't exist yet. `landmark`'s chain
(`theme` → `landmark_category` → `landmark`) is independent of sensors
entirely. `run_pipeline.py` already does this in the right order — this
only matters if you're running scripts individually.

---

## One-time local setup

1. Install Postgres (Windows installer, bundles pgAdmin).
2. In pgAdmin's Query Tool (or `psql -U postgres`), run:
   ```sql
   CREATE USER clearway WITH PASSWORD 'clearway_dev' SUPERUSER;
   CREATE DATABASE clearway OWNER clearway;
   ```
3. `pip install -r requirements.txt`
4. Copy `.env.example` → `.env` (values already match step 2's defaults).
5. Create `data/` folder next to the scripts, drop in the 4 CSVs with their
   original filenames.

---

## Testing / verification, step by step

**Always start from a clean slate** if you're not sure what state the DB
is in — it's cheap and avoids foreign-key errors from stale data:
```
python build_schema.py --reset
```

**Run the full pipeline:**
```
python run_pipeline.py --reset
```
Expected console output (row counts will match your CSV snapshot exactly):
```
sensor_location: loaded 134 sensors (134 active)
pedestrian_minute_count: loaded 664506 rows ...
  backfilled 3 sensor_location stub row(s) for decommissioned/unknown sensors ...
pedestrian_hourly_count: loaded 1613800 rows ...
  note: 9 landmark(s) share a Feature Name + Theme + Sub Theme ...
landmark: loaded 242 landmarks across 49 theme/sub-theme combos (37 flagged as refuges ...)
```

**Verify in pgAdmin's Query Tool** (easier than the `psql` terminal — see
gotchas below). Connect to the `clearway` database specifically, then:

```sql
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
-- expect 6 rows: sensor_location, pedestrian_hourly_count,
-- pedestrian_minute_count, theme, landmark_category, landmark

SELECT COUNT(*) FROM sensor_location;             -- 134 + any decommissioned backfills (e.g. 137)
SELECT COUNT(*) FROM pedestrian_hourly_count;      -- matches pipeline's printed row count
SELECT COUNT(*) FROM pedestrian_minute_count;      -- matches pipeline's printed row count
SELECT COUNT(*) FROM landmark;                     -- matches pipeline's printed row count
SELECT COUNT(*) FROM landmark_category WHERE is_refuge = true;  -- 1 (Park/Garden only, current scope)
```

**Sanity check the data itself looks real, not just present:**
```sql
SELECT * FROM sensor_location LIMIT 5;
SELECT feature_name, category_name
FROM landmark JOIN landmark_category USING (category_id)
WHERE is_refuge = true LIMIT 5;
```

If every number above matches what the pipeline printed to the console,
your local database is fully verified.

---

## Common gotchas

- **`psql` not found** → not on Windows PATH. Either use the full path
  (`"C:\Program Files\PostgreSQL\16\bin\psql.exe"`), add that folder to
  PATH, or just use pgAdmin's Query Tool instead — simplest option.
- **SQL typed into PowerShell by mistake** → `SELECT * FROM ...` is SQL,
  not a PowerShell command. Run it inside `psql` or pgAdmin's Query Tool,
  never the plain terminal prompt.
- **`\dt` shows no tables** → you're connected to the wrong database.
  Plain `psql` defaults to the `postgres` database, not `clearway`. Run
  `\conninfo` to check, `\c clearway` to switch, or reconnect with
  `psql -U clearway -d clearway -h localhost` (note the `-d` flag).
- **Wrong password for `clearway`** → it's `clearway_dev` (set manually
  when the user was created), not your Postgres installer password —
  those are two separate accounts. Check `.env` if unsure.
- **Foreign key violation on re-running a single ingest script** → other
  tables still reference the data you're trying to delete. Run
  `python build_schema.py --reset` first to clear everything together,
  rather than re-running one script against a partially loaded DB.

---

## Open decisions for the team (not yet resolved)

- **Refuge scope**: currently Park/Garden/Reserve only. Library and
  Art Gallery/Museum were considered, deliberately deferred — see
  `config.REFUGE_THEME_SUBTHEME_PAIRS` to expand later.
- **Scoring tiers**: pipeline/scoring code outputs binary Low/High,
  matching the locked user story wording. `docs/api/api-contract.md`
  currently documents a three-tier LOW/MEDIUM/HIGH — this conflict needs
  resolving with whoever owns that doc.
- **Real-time ingestion**: the pipeline currently reads static downloaded
  CSVs. Turning this into an actually-live feed needs two things nobody's
  built yet: a client for Melbourne's live Open Data API (stub exists at
  `services/api/src/clients/open_data_client.py`), and a scheduler
  (EventBridge, roughly every 15 minutes) to re-run ingestion on a timer.
- **Lambda packaging**: the pipeline depends on `pandas` and
  `psycopg2-binary`, which the repo's current Terraform Lambda setup
  can't package (no layer, no requirements.txt bundling). Needs an infra
  decision — Lambda Layer vs. a scheduled Fargate task — before this can
  actually be deployed to AWS.
