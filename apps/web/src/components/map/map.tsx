"use client"

import dynamic from "next/dynamic"
import type { Coordinates, Refuge, Route } from "@clearway/shared"

const LeafletMap = dynamic(
  () =>
    import("@/components/map/leaflet-map").then(
      (module) => module.LeafletMap
    ),
  {
    ssr: false,
    loading: () => (
      <div
        className="h-full w-full animate-pulse bg-muted"
        aria-label="Loading map"
      />
    ),
  }
)

interface MapProps {
  origin?: Coordinates | null
  destination?: Coordinates | null
  refuges?: Refuge[]
  routes?: Route[]
  selectedRouteId?: string | null
  onRouteSelect?: (routeId: string) => void
}

export function Map({
  origin,
  destination,
  refuges,
  routes,
  selectedRouteId,
  onRouteSelect,
}: MapProps) {
  return (
    <LeafletMap
      origin={origin}
      destination={destination}
      refuges={refuges}
      routes={routes}
      selectedRouteId={selectedRouteId}
      onRouteSelect={onRouteSelect}
    />
  )
}
