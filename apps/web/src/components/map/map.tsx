"use client"

import dynamic from "next/dynamic"
import type { Coordinates, Refuge } from "@clearway/shared"

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
  refuges?: Refuge[]
}

export function Map({ origin, refuges }: MapProps) {
  return <LeafletMap origin={origin} refuges={refuges} />
}
