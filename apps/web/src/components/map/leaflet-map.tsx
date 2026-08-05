"use client"

import { useEffect } from "react"
import { MapContainer, TileLayer, useMap } from "react-leaflet"
import { useGeolocation } from "@/hooks/use-geolocation"

const DEFAULT_POSITION: [number, number] = [-37.8136, 144.9631]

// Helper component to update the map view dynamically when center changes
function ChangeMapView({ center }: { center: [number, number] }) {
  const map = useMap()
  useEffect(() => {
    map.setView(center, map.getZoom())
  }, [center, map])
  return null
}

export function LeafletMap() {
  const { position } = useGeolocation(DEFAULT_POSITION)

  return (
    <MapContainer
      center={DEFAULT_POSITION}
      zoom={13}
      scrollWheelZoom
      className="h-full w-full"
    >
      <ChangeMapView center={position} />
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
    </MapContainer>
  )
}