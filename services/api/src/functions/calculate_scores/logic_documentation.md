# Scoring Logic — What It Does and How We Tested It

**Covers:** US1.1 (sensory indicator), US1.2 (avoid high-density corridors)
**Location:** `services/api/src/functions/calculate_scores/scoring_logic.py`
**Tests:** `services/api/tests/test_score.py` (10 test cases)

---

## What it does

Gives each sensor a **High** or **Low** score, based on its own past data.
We do not use one fixed number for every sensor. Each sensor gets its own
normal range, based on its own history.

**Steps, in order:**
1. **Threshold** — for each sensor, we find the top 25% (75th percentile) of
   its own past hourly counts (`pedestrian_hourly_count`). This is the
   "busy" line, for that one sensor only.
2. **Current reading** — we add up the last 60 minutes of live counts for
   that sensor (`pedestrian_minute_count`). This gives us a "per hour"
   number, so it matches the threshold.
3. **Classify** — we compare the current reading to the threshold. Higher =
   High. Lower = Low.
4. **Fallback** — if a sensor has no current reading (e.g. old data, or the
   sensor was offline), we use that sensor's own past average instead. This
   way the app still gives an answer, instead of failing.

**Why we use a top-25% number, not a fixed number or an average:**
Some streets are always busy, some are always quiet. A fixed number would
call the busy street "always High" and the quiet one "never High." Using
each sensor's own top-25% means "High" really means "busier than usual for
this street," not just "a big number."

**Why we use 60 minutes, not just one minute of data:**
The threshold is a "per hour" number. If we compared it to just one minute
of data, the numbers would not match, and the score would always look too
low. This was an early bug — see below.

**Note on where the data comes from:**
Our functions only read from Postgres tables (`pedestrian_hourly_count`,
`pedestrian_minute_count`). They do not know or care how that data got
into Postgres. Right now, the pipeline loads both tables from downloaded
CSV files (`source="csv"`, the default in `ingest_pedestrian_minute.py`).
A live API client already exists (`clients/open_data_client.py`,
`source="api"`), but `run_pipeline.py` does not use it yet. Once someone
switches the pipeline to live mode, our scoring functions will work the
same way, with no changes needed — they were built to depend only on the
table structure, not on where the rows came from.

---

## Functions

| Function | What it does |
|---|---|
| `_location_filter` | Builds the right SQL filter for one sensor, a list, or all sensors |
| `fetch_hourly_history` | Reads past hourly counts from Postgres |
| `fetch_recent_minutes` | Reads recent minute-level counts from Postgres |
| `calculate_thresholds` | Works out each sensor's top-25% threshold |
| `get_last_hour_total` | Adds up the last 60 minutes per sensor |
| `classify_current_conditions` | Compares reading to threshold, uses fallback if needed |
| `get_scores` | Runs all the steps together, for one sensor, a list, or all sensors |

`get_scores` can be called three ways:
```python
get_scores(63)          # one sensor
get_scores([63, 4, 9])  # a list (e.g. sensors along one route)
get_scores()            # every sensor
```

---

## How we tested it

### 1. Unit tests (10 cases, no database needed)
Run with: `python services/api/tests/test_score.py`

Tests cover: the SQL filter (all 3 input types), threshold calculation,
last-hour summing (including a regression test, see below), fallback
behaviour, the full pipeline running together, and two edge cases (every
sensor falling back at once, and a sensor with only one past reading).

**Result: 10/10 passing.**

Note: this is rule-based logic, not a predictive model, so there is no
"accuracy rate" to report the way there would be for a trained model. We
checked correctness in the ways listed below instead.

### 2. Testing against real data (Colab, real City of Melbourne CSVs)
- Ran each function on real data from 101 sensors
- Checked one result by hand: sensor 1, reading 1650 vs threshold 1750.5 →
  correctly came back Low
- Found 3 sensors with no live reading, and confirmed they correctly used
  their real past average instead (sensor 78, 108, 124)
- Compared the same logic at two different times: 1% High at 3am vs 37%
  High at 4:34pm on a weekday — matches what a real commute pattern should
  look like

### 3. A bug we found and fixed
**Problem:** `get_last_hour_total`, when called without an explicit
`reference_time` (the normal way it gets called in real use), compared
against the unset value instead of the calculated one. This caused a
crash on real timezone-aware data.

**How we found it:** testing against real data in Colab. Our original
unit tests did not catch this, because they always passed
`reference_time` in manually.

**Fix:** corrected the line, and added a new test that calls the function
the normal way (no `reference_time` passed), so this bug cannot come back
without a test failing.

### 4. Testing against a real, local database
Ran the full pipeline: `build_schema.py` → `run_pipeline.py` → real
Postgres, then called `get_scores()` all three ways directly against it.

**Result:** all three ways worked correctly. All 101 sensors correctly
used fallback, because our local data snapshot was older than the actual
current time. This is a good real-world check that fallback works, not
just in theory.

**Note on test scope:** all testing so far (Colab and local database) used
data loaded from CSV files, since that is what `run_pipeline.py` currently
does. We have not tested against data loaded from the live API path
(`source="api"`), since that path is not wired into the pipeline yet.
Based on the code (see note above), we expect no difference, since our
functions only read from the Postgres tables, not from the original
source — but this should be re-confirmed once someone switches the
pipeline to live mode.

---

## Known limits / not done yet

- **Threshold data isn't a full year yet.** Our export is for "2026," but
  since today is only August 2026, we actually only have about 5–8 months
  of data per sensor, not 12. This means the threshold may not fully
  capture how the season changes (e.g. summer vs winter foot traffic).
  Worth re-checking once a full year of data is available.
- **Real-time data source.** The pipeline currently reads a downloaded
  CSV, not live data. A teammate built a live API client
  (`clients/open_data_client.py`), and the ingest script supports it, but
  `run_pipeline.py` is not yet set up to use it.
- **Not deployed to Lambda yet.** `calculate_scores` is not in `lambda.tf` yet