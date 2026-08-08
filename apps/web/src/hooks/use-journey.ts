import { useState } from "react"
import type { LocationSuggestion } from "@clearway/shared"

import { MOCK_ROUTES } from "@/lib/mock-routes"

export function useJourney() {
  const [origin, setOriginState] = useState<LocationSuggestion | null>(null)
  const [destination, setDestinationState] = useState<LocationSuggestion | null>(null)
  const [activeFilter, setActiveFilter] = useState<"all" | "Low" | "Medium" | "High">("all")
  const [hasSearched, setHasSearched] = useState(false)

  const filteredRoutes = hasSearched
    ? MOCK_ROUTES.filter(
        (route) => activeFilter === "all" || route.crowdLevel === activeFilter
      )
    : []

  const setOrigin = (location: LocationSuggestion | null) => {
    setOriginState(location)
    setHasSearched(false)
  }

  const setDestination = (location: LocationSuggestion | null) => {
    setDestinationState(location)
    setHasSearched(false)
  }

  const searchJourney = () => {
    if (origin && destination) setHasSearched(true)
  }

  const toggleFilter = (filter: "Low" | "Medium" | "High") => {
    setActiveFilter((prev) => (prev === filter ? "all" : filter))
  }

  return {
    origin,
    setOrigin,
    destination,
    setDestination,
    canSearch: origin !== null && destination !== null,
    hasSearched,
    searchJourney,
    activeFilter,
    filteredRoutes,
    toggleFilter,
  }
}
