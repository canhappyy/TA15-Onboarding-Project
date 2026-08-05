"use client"

import { MapContainer, TileLayer } from "react-leaflet"

const DEFAULT_POSITION: [number, number] = [-37.8136, 144.9631]

export function LeafletMap() {
  return (
    <MapContainer
      center={DEFAULT_POSITION}
      zoom={13}
      scrollWheelZoom
      className="h-full w-full"
    >
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
    </MapContainer>
  )
}