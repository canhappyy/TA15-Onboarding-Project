# Clearway API contract

Version: 1.0

Base URL: `https://<api-gateway-url>`

This document locks future public endpoint shapes. Except for `GET /health`, all endpoints return the common envelope below. Endpoints may remain unavailable until their implementation milestones land.

## Common envelope

Success:

```json
{"success":true,"data":{}}
```

Failure:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Origin is required."
  }
}
```

Every response uses `Content-Type: application/json`.

## Error codes

| Code | Typical HTTP status | Meaning |
| --- | ---: | --- |
| `INVALID_REQUEST` | 400 | Request parameters or body are invalid. |
| `OUTSIDE_SERVICE_AREA` | 400 | Location is outside the City of Melbourne boundary. |
| `NOT_FOUND` | 404 | Requested resource does not exist. |
| `UPSTREAM_TIMEOUT` | 504 | An upstream provider timed out. |
| `UPSTREAM_ERROR` | 502 | An upstream provider failed or returned malformed data. |
| `DATA_UNAVAILABLE` | 503 | Required application data is unavailable. |
| `TOO_MANY_REQUESTS` | 429 | Rate limit exceeded. |
| `INTERNAL_SERVER_ERROR` | 500 | Unexpected server error. |

## Shared values

Coordinates use `{ "latitude": number, "longitude": number }`.

GeoJSON route geometry uses a `LineString`. Each position is `[longitude, latitude]`.

Sensory indicators are only `LOW` or `HIGH`.

Freshness uses:

```json
{
  "observedAt": "2026-08-08T10:15:00+10:00",
  "stale": false,
  "fallbackUsed": false
}
```

`observedAt` may be `null` when no observation timestamp is available.

## `GET /health`

Deployment and monitoring probe. This is the only endpoint outside the common envelope.

```json
{"status":"ok"}
```

## `GET /locations/search?text=<query>`

Returns at most five OpenRouteService suggestions inside the City of Melbourne boundary.
The service returns `OUTSIDE_SERVICE_AREA` when matches exist but all are outside
the municipal boundary. No upstream matches return an empty suggestions array.

```json
{
  "success": true,
  "data": {
    "suggestions": [
      {
        "id": "ors-place-id",
        "label": "State Library Victoria, Melbourne VIC",
        "coordinates": {
          "latitude": -37.8098,
          "longitude": 144.9652
        }
      }
    ]
  }
}
```

Boundary source: City of Melbourne Open Data, `municipal-boundary`, Creative
Commons Attribution. The packaged 2022 export avoids a runtime dependency on
the boundary dataset.

## `POST /routes/search`

Request:

```json
{
  "origin": {"latitude": -37.8179, "longitude": 144.9671},
  "destination": {"latitude": -37.8098, "longitude": 144.9652}
}
```

Response:

```json
{
  "success": true,
  "data": {
    "routes": [
      {
        "id": "route-1",
        "durationMinutes": 18,
        "walkingDistanceKm": 1.3,
        "score": 24,
        "indicator": "LOW",
        "geometry": {
          "type": "LineString",
          "coordinates": [[144.9671, -37.8179], [144.9652, -37.8098]]
        },
        "recommended": true,
        "warning": null,
        "explanation": "Calculated using pedestrian crowd information and nearby refuge availability.",
        "freshness": {
          "observedAt": "2026-08-08T10:15:00+10:00",
          "stale": false,
          "fallbackUsed": false
        }
      }
    ]
  }
}
```

Accepted journeys return at least two distinct candidate routes. Routes sort by sensory score ascending, then duration ascending. Every route remains selectable. `warning` is non-null when high pedestrian density or stale/unavailable live data must be disclosed.

The current provisional score uses 85% pedestrian-density exposure and 15%
nearby-refuge coverage. Team or mentor approval of these weights remains a
release gate. Live data is stale when the latest matched-sensor observation is
missing or older than 30 minutes.

## `POST /refuges/search`

Returns refuges within one kilometre of a journey route.

Request:

```json
{
  "origin": {"latitude": -37.8179, "longitude": 144.9671},
  "route": {
    "type": "LineString",
    "coordinates": [[144.9671, -37.8179], [144.9652, -37.8098]]
  },
  "categories": ["LIBRARY", "PARK"]
}
```

Response uses the refuge shape documented under `GET /refuges`.

## `GET /refuges`

Query parameters:

| Parameter | Required | Meaning |
| --- | --- | --- |
| `latitude` | Yes | Search-origin latitude. |
| `longitude` | Yes | Search-origin longitude. |
| `category` | No | `LIBRARY`, `MUSEUM`, `GARDEN`, or `PARK`. |

Returns at most 20 refuges within one kilometre.

```json
{
  "success": true,
  "data": {
    "refuges": [
      {
        "id": "landmark-102",
        "name": "State Library Victoria",
        "category": "LIBRARY",
        "coordinates": {"latitude": -37.8098, "longitude": 144.9652},
        "walkingDistanceKm": 0.45,
        "metadata": {"source": "City of Melbourne Open Data"},
        "navigationUrl": "https://www.google.com/maps/dir/?api=1&destination=-37.8098,144.9652"
      }
    ]
  }
}
```

## `GET /congestion`

Returns current or fallback pedestrian conditions.

```json
{
  "success": true,
  "data": {
    "sensors": [
      {
        "id": "34",
        "name": "Flinders Street",
        "indicator": "HIGH",
        "pedestrianCount": 158,
        "coordinates": {"latitude": -37.817, "longitude": 144.967},
        "freshness": {
          "observedAt": "2026-08-08T10:15:00+10:00",
          "stale": false,
          "fallbackUsed": false
        }
      }
    ],
    "freshness": {
      "observedAt": "2026-08-08T10:15:00+10:00",
      "stale": false,
      "fallbackUsed": false
    },
    "staleWarning": null
  }
}
```

The canonical TypeScript definitions are in `packages/shared/src/index.ts`.
