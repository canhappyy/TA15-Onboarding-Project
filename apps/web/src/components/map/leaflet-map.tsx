"use client"

import { useEffect } from "react"
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet"
import type { Coordinates, Refuge } from "@clearway/shared"

const DEFAULT_POSITION: [number, number] = [-37.8136, 144.9631]

// Helper component to update the map view dynamically when center changes
function ChangeMapView({ center }: { center: [number, number] }) {
  const map = useMap()
  useEffect(() => {
    map.setView(center, map.getZoom())
  }, [center, map])
  return null
}

interface LeafletMapProps {
  origin?: Coordinates | null
  refuges?: Refuge[]
}

export function LeafletMap({ origin, refuges = [] }: LeafletMapProps) {
  const center: [number, number] = origin
    ? [origin.latitude, origin.longitude]
    : DEFAULT_POSITION

  return (
    <MapContainer
      center={DEFAULT_POSITION}
      zoom={13}
      scrollWheelZoom
      className="h-full w-full"
    >
      <ChangeMapView center={center} />
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {refuges.map((refuge) => (
        <CircleMarker
          key={refuge.id}
          center={[refuge.coordinates.latitude, refuge.coordinates.longitude]}
          radius={8}
          pathOptions={{ color: "#475569", fillColor: "#8da2cf", fillOpacity: 0.9 }}
        >
          <Popup>
            <strong>{refuge.name}</strong>
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
