import { useState } from "react"
import { MOCK_QUIET_SPACES, type QuietSpace } from "@/lib/mock-quiet-spaces"

export type QuietSpaceFilter = "all" | "Park" | "Library" | "Cafe"

export function useQuietSpaces() {
  const [activeFilter, setActiveFilter] = useState<QuietSpaceFilter>("all")

  const filteredQuietSpaces = MOCK_QUIET_SPACES.filter(
    (space) => activeFilter === "all" || space.category === activeFilter
  )

  const toggleFilter = (filter: QuietSpaceFilter) => {
    setActiveFilter(filter)
  }

  return {
    activeFilter,
    filteredQuietSpaces,
    toggleFilter,
  }
}
