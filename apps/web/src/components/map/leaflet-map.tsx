"use client"

import { useEffect, useMemo } from "react"
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap } from "react-leaflet"
import type { Coordinates, Refuge, Route } from "@clearway/shared"

const DEFAULT_POSITION: [number, number] = [-37.8136, 144.9631]
const EMPTY_REFUGES: Refuge[] = []
const EMPTY_ROUTES: Route[] = []

// Helper component to update the map view dynamically when center changes
function ChangeMapView({
  center,
  journeyBoundsPositions,
}: {
  center: [number, number]
  journeyBoundsPositions: [number, number][]
}) {
  const map = useMap()
  useEffect(() => {
    if (journeyBoundsPositions.length >= 2) {
      map.fitBounds(journeyBoundsPositions, { padding: [24, 24] })
      return
    }
    map.setView(center, map.getZoom())
  }, [center, journeyBoundsPositions, map])
  return null
}

function formatRefugeCategory(category: Refuge["category"]) {
  return category[0] + category.slice(1).toLowerCase()
}

interface LeafletMapProps {
  origin?: Coordinates | null
  destination?: Coordinates | null
  refuges?: Refuge[]
  routes?: Route[]
  selectedRouteId?: string | null
  onRouteSelect?: (routeId: string) => void
}

export function LeafletMap({
  origin,
  destination,
  refuges = EMPTY_REFUGES,
  routes = EMPTY_ROUTES,
  selectedRouteId,
  onRouteSelect,
}: LeafletMapProps) {
  const center = useMemo<[number, number]>(
    () => origin
      ? [origin.latitude, origin.longitude]
      : DEFAULT_POSITION,
    [origin]
  )
  const journeyBoundsPositions = useMemo<[number, number][]>(
    () => {
      const routePositions = routes.flatMap((route) =>
        route.geometry.coordinates.map(
          ([longitude, latitude]): [number, number] => [latitude, longitude]
        )
      )

      return routePositions.length >= 2
        ? [
            ...routePositions,
            ...refuges.map(
              (refuge): [number, number] => [
                refuge.coordinates.latitude,
                refuge.coordinates.longitude,
              ]
            ),
          ]
        : routePositions
    },
    [refuges, routes]
  )
  const orderedRoutes = [
    ...routes.filter((route) => route.id !== selectedRouteId),
    ...routes.filter((route) => route.id === selectedRouteId),
  ]

  return (
    <MapContainer
      center={DEFAULT_POSITION}
      zoom={13}
      scrollWheelZoom
      className="h-full w-full"
    >
      <ChangeMapView
        center={center}
        journeyBoundsPositions={journeyBoundsPositions}
      />
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {orderedRoutes.map((route) => {
        const selected = route.id === selectedRouteId
        return (
          <Polyline
            key={route.id}
            positions={route.geometry.coordinates.map(
              ([longitude, latitude]) => [latitude, longitude]
            )}
            pathOptions={{
              color: selected ? "#475569" : "#94a3b8",
              opacity: selected ? 0.95 : 0.6,
              weight: selected ? 6 : 4,
            }}
            eventHandlers={{ click: () => onRouteSelect?.(route.id) }}
          />
        )
      })}
      {routes.length > 0 && origin ? (
        <CircleMarker
          center={[origin.latitude, origin.longitude]}
          radius={7}
          pathOptions={{ color: "#0f766e", fillColor: "#14b8a6", fillOpacity: 1 }}
        >
          <Popup>Origin</Popup>
        </CircleMarker>
      ) : null}
      {routes.length > 0 && destination ? (
        <CircleMarker
          center={[destination.latitude, destination.longitude]}
          radius={7}
          pathOptions={{ color: "#b91c1c", fillColor: "#ef4444", fillOpacity: 1 }}
        >
          <Popup>Destination</Popup>
        </CircleMarker>
      ) : null}
      {refuges.map((refuge) => (
        <CircleMarker
          key={refuge.id}
          center={[refuge.coordinates.latitude, refuge.coordinates.longitude]}
          radius={8}
          pathOptions={{ color: "#475569", fillColor: "#8da2cf", fillOpacity: 0.9 }}
        >
          <Popup>
            <strong>{refuge.name}</strong>
            <p>{formatRefugeCategory(refuge.category)}</p>
            <p>{refuge.walkingDistanceKm.toFixed(1)} km away</p>
            <a
              href={refuge.navigationUrl}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Navigate to ${refuge.name}`}
            >
              Navigate
            </a>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
