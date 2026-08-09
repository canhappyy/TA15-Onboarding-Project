# Pipeline-to-API database contract

The ingestion pipeline owns writes. Public API handlers and repositories use read-only database access.

Route search authenticates as `clearway_route_api`, which inherits only the
`clearway_api_readonly` role. That role has database connection, schema usage,
and table `SELECT`; it has no data mutation or schema creation grants.

## Sensors and live totals

- Only active sensors with valid latitude and longitude are eligible.
- Live totals use observed minute rows only.
- Rows with `is_imputed = true` are excluded from live totals.
- Missing observations remain missing; they are never treated as zero pedestrians.
- Freshness derives from the latest eligible minute timestamp.

## History and fallback

- Hourly history supplies missing-live fallback values and per-sensor baselines.
- Baselines use the latest 90 days of hourly history.
- All ingestion and query timestamps are PostgreSQL `TIMESTAMPTZ` values.
- API responses serialize timestamps with an explicit UTC offset.

## Refuges

- The API reads stored landmark name, theme, sub-theme, latitude, longitude, and source metadata.
- The API layer maps stored theme and sub-theme values to `LIBRARY`, `MUSEUM`, `GARDEN`, or `PARK`.
- Unknown categories are not returned as supported refuges.

## Privacy

- User locations and journeys are request-only data.
- The API and database never persist user locations, routes, journeys, or identifiers.
- Logs must not include exact user coordinates or journey geometry.
