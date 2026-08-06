import { useState } from "react"
import { MOCK_ROUTES, type Route } from "@/lib/mock-routes"

export function useJourney() {
  const [origin, setOrigin] = useState("Current location")
  const [destination, setDestination] = useState("Flinders St Station")
  const [activeFilter, setActiveFilter] = useState<"all" | "Low" | "High">("all")

  const filteredRoutes = MOCK_ROUTES.filter(
    (route) => activeFilter === "all" || route.crowdLevel === activeFilter
  )

  const toggleFilter = (filter: "Low" | "High") => {
    setActiveFilter((prev) => (prev === filter ? "all" : filter))
  }

  return {
    origin,
    setOrigin,
    destination,
    setDestination,
    activeFilter,
    filteredRoutes,
    toggleFilter,
  }
}
