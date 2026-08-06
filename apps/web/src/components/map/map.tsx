"use client"

import dynamic from "next/dynamic"

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

export function Map() {
  return <LeafletMap />
}