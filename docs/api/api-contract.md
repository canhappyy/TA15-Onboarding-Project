# Sensory Navigation API Specification

Version: 1.0
Base URL:
https://<api-gateway-url>/v1

## Overview

This API provides data required by the Sensory Navigation application.

The frontend communicates only with this API. The backend is responsible for:

- retrieving data from City of Melbourne Open Data APIs
- retrieving and caching processed data from PostgreSQL
- calculating congestion levels
- calculating sensory indicators
- returning nearby sensory refuge locations

---

# Common Response Format

Success

```json
{
  "success": true,
  "data": {}
}
```

Error

```json
{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Origin is required."
  }
}
```

---

# Error Codes

| HTTP | Code                  | Description                       |
| ---- | --------------------- | --------------------------------- |
| 400  | INVALID_REQUEST       | Request validation failed         |
| 404  | NOT_FOUND             | Requested resource does not exist |
| 429  | TOO_MANY_REQUESTS     | Rate limit exceeded               |
| 500  | INTERNAL_SERVER_ERROR | Unexpected server error           |

---

# 1. Health Check

## GET /health

Used by monitoring and deployment verification.

### Response

```json
{
  "status": "ok"
}
```

---

# 2. Search Routes

## POST /routes/search

Returns candidate walking routes between an origin and destination enriched with sensory information.

This endpoint supports:

- US1.1
- US1.2

### Request

```json
{
  "origin": {
    "latitude": -37.911,
    "longitude": 145.134
  },
  "destination": {
    "latitude": -37.814,
    "longitude": 144.963
  }
}
```

### Response

```json
{
  "success": true,
  "data": {
    "routes": [
      {
        "routeId": "route-1",
        "distanceMeters": 3400,
        "durationMinutes": 47,
        "sensoryLevel": "LOW",
        "congestionLevel": "LOW",
        "crowdScore": 24,
        "geometry": {
          "type": "LineString",
          "coordinates": []
        }
      },
      {
        "routeId": "route-2",
        "distanceMeters": 3000,
        "durationMinutes": 43,
        "sensoryLevel": "HIGH",
        "congestionLevel": "HIGH",
        "crowdScore": 176,
        "geometry": {
          "type": "LineString",
          "coordinates": []
        }
      }
    ]
  }
}
```

### Business Rules

- Return at most 3 routes.
- Sort by shortest travel time.
- Crowd score is derived from nearby pedestrian sensors.
- Sensory level is calculated from crowd score.

---

# 3. Nearby Sensory Refuges

## GET /refuges

Returns nearby sensory refuge locations.

Supports:

- US2.1

### Query Parameters

| Parameter | Required | Description                            |
| --------- | -------- | -------------------------------------- |
| latitude  | Yes      | Current latitude                       |
| longitude | Yes      | Current longitude                      |
| radius    | No       | Search radius in metres (default 1000) |

Example

```
GET /refuges?latitude=-37.814&longitude=144.963&radius=1000
```

### Response

```json
{
  "success": true,
  "data": {
    "refuges": [
      {
        "id": 102,
        "name": "State Library Victoria",
        "category": "LIBRARY",
        "latitude": -37.809,
        "longitude": 144.965,
        "distanceMeters": 450
      },
      {
        "id": 211,
        "name": "Carlton Gardens",
        "category": "PARK",
        "latitude": -37.806,
        "longitude": 144.971,
        "distanceMeters": 610
      }
    ]
  }
}
```

---

# 4. Current Congestion

## GET /congestion

Returns current congestion information from pedestrian sensors.

### Query Parameters

| Parameter | Required | Description  |
| --------- | -------- | ------------ |
| bbox      | No       | Bounding box |

Example

```
GET /congestion?bbox=144.95,-37.82,144.98,-37.80
```

### Response

```json
{
  "success": true,
  "data": {
    "generatedAt": "2026-08-05T10:15:00Z",

    "sensors": [
      {
        "sensorId": 34,
        "sensorName": "Flinders Street",
        "latitude": -37.817,
        "longitude": 144.967,
        "pedestrianCount": 158,
        "congestionLevel": "HIGH",
        "sensoryLevel": "HIGH"
      }
    ]
  }
}
```

---

# Sensory Classification

The backend derives sensory levels from pedestrian counts.

| Pedestrian Count | Sensory Level |
| ---------------- | ------------- |
| 0-50             | LOW           |
| 51-150           | MEDIUM        |
| 151+             | HIGH          |

---

# Data Sources

The backend integrates:

- Pedestrian Counting System - Past Hour (Counts per Minute)
- Pedestrian Counting System - Sensor Locations
- Pedestrian Counting System - Monthly Counts per Hour
- Landmarks and Places of Interest

The frontend never communicates directly with external APIs.

---

# Authentication

Current Version

No authentication required.

Future Version

API Gateway JWT Authorizer (Amazon Cognito)

---

# Rate Limits

100 requests / minute / IP

---

# Versioning

Current Version

```
/v1
```

Future breaking changes will be released under:

```
/v2
```
