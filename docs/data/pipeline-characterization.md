# Pipeline characterization

## Purpose and ownership

The files in `services/api/src/pipeline` are teammate-owned local CSV prototypes. This milestone does not modify them. The characterization suite records their current behavior before valid transformations are ported into a separate, lightweight ingestion package.

Passing characterization tests means the behavior is reproduced. It does not approve that behavior for scheduled production ingestion.

## Sources and field mappings

| Dataset       | Source fields                                                     | Stored fields                                      |
| ------------- | ----------------------------------------------------------------- | -------------------------------------------------- |
| Sensors       | `Location_ID`, sensor metadata, status, latitude, longitude       | `sensor_location` columns in snake case            |
| Minute counts | `Location_ID`, `Sensing_DateTime`, direction counts, total        | `pedestrian_minute_count`                          |
| Hourly counts | `Location_ID`, `Sensing_Date`, `HourDay`, direction counts, total | `pedestrian_hourly_count` with a derived timestamp |
| Landmarks     | `Theme`, `Sub Theme`, `Feature Name`, `Co-ordinates`              | `theme`, `landmark_category`, `landmark`           |

Fixtures live in `services/api/tests/fixtures/pipeline`. `expectations.json` deliberately separates `legacy` output from the `target` required by scheduled ingestion.

## Current acceptance and rejection rules

### Sensors

- Text fields are trimmed.
- Rows without `location_id` are dropped.
- Invalid coordinates and installation dates become null.
- Duplicate identifiers keep the last source row.
- The loader deletes the entire sensor table before inserting its result.

### Minute counts

- Source columns are renamed to database columns.
- Duplicate `(sensing_datetime, location_id)` readings keep the last row.
- Each source timestamp is expanded across every active sensor.
- Missing sensor readings are written as zero with `is_imputed=true`.
- CSV mode deletes all minute rows; API mode stages a frame and upserts it.

### Hourly counts

- Input is read in chunks.
- Duplicate `(location_id, sensing_datetime)` rows keep the first row within a chunk.
- Historical sensor identifiers absent from metadata receive inactive stub records.
- Missing hours remain absent.
- Timestamps use `Australia/Melbourne`, producing `+10:00` in winter and `+11:00` in summer.
- Existing hourly rows are deleted before the load.

### Landmarks

- Theme, sub-theme, and feature names are trimmed.
- Rows missing any required classification or name are dropped.
- Invalid coordinates become null.
- Repeated feature names are retained because they may represent separate entrances.
- Only the configured Park/Garden/Reserve pair is marked as a refuge.
- Landmark tables are deleted and identity sequences reset before insertion.

## Reuse and isolation matrix

| Area                             | Current behavior                               | Production decision                                                       |
| -------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------- |
| Column mapping                   | Valid                                          | Port unchanged                                                            |
| Text trimming                    | Valid                                          | Port unchanged                                                            |
| Sensor duplicate precedence      | Valid                                          | Port unchanged                                                            |
| Coordinate parsing               | Valid                                          | Port unchanged                                                            |
| Historical sensor backfill       | Valid                                          | Port unchanged                                                            |
| Chunked hourly processing        | Valid concept                                  | Preserve bounded batches                                                  |
| Table-wide deletion              | Unsafe for schedules and foreign keys          | Replace in new repository with upserts                                    |
| Missing minute to zero           | Hides unavailable data and can bias scores Low | Omit missing rows in new normalizer                                       |
| Melbourne timezone localization | Valid                                          | Port unchanged                                                            |
| Park/Garden-only refuge flag     | Incomplete for US2.1                           | Retain raw classification and map required categories outside legacy code |
| pandas and SQLAlchemy coupling   | Too heavy for the planned Lambda ZIP           | Use plain dictionaries and psycopg in new ingestion code                  |
| Source-latest five-minute window | Can miss records after delayed runs            | Use checkpoint watermark plus overlap in new sync client                  |

## Target ingestion contract

The future ingestion normalizers will use the `target` entries in `expectations.json`:

- Inputs and outputs are plain dictionaries and lists.
- Invalid rows are rejected and counted without aborting valid rows.
- Missing observations are not manufactured.
- Aware Melbourne timestamps are stored as PostgreSQL `TIMESTAMPTZ`; the summer fixture therefore uses `+11:00`.
- Sensors, counts, and landmarks use stable conflict-safe upserts.
- Library, Museum, Garden, and Park remain identifiable from raw theme/sub-theme values.
- Network fetching, normalization, and database writing remain separate units.

No ORM is planned for production ingestion. Existing SQLAlchemy use remains confined to the teammate-owned local prototype; scheduled Lambdas will reuse the psycopg layer and explicit PostgreSQL upserts.

## Running the suite

From `services/api` after installing `requirements-dev.txt`:

```bash
pytest tests/pipeline
```

Tests mock database connections and API data. They require no PostgreSQL instance, AWS account, or live City of Melbourne request.
