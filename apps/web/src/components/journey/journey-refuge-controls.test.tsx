import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { Refuge } from "@clearway/shared"
import { afterEach, describe, expect, it, vi } from "vitest"

import { JourneyRefugeControls } from "@/components/journey/journey-refuge-controls"

const park: Refuge = {
  id: "park.1",
  name: "Treasury Gardens",
  category: "PARK",
  coordinates: { latitude: -37.8146, longitude: 144.9681 },
  walkingDistanceKm: 0.6,
  metadata: { source: "City of Melbourne Open Data" },
  navigationUrl: "https://maps.example/treasury",
}

const museum: Refuge = {
  ...park,
  id: "museum.1",
  name: "Melbourne Museum",
  category: "MUSEUM",
}

function renderControls(overrides: Partial<React.ComponentProps<typeof JourneyRefugeControls>> = {}) {
  const props: React.ComponentProps<typeof JourneyRefugeControls> = {
    refuges: [park, museum],
    filteredRefuges: [park, museum],
    activeFilter: "all",
    loading: false,
    error: null,
    hasSearched: true,
    onToggleFilter: vi.fn(),
    onRetry: vi.fn(),
    ...overrides,
  }

  return { ...render(<JourneyRefugeControls {...props} />), props }
}

afterEach(cleanup)

describe("JourneyRefugeControls", () => {
  it("labels its region and shows all refuge categories", () => {
    renderControls()

    expect(screen.getByRole("region", { name: "Quiet spaces along this route" })).toBeInTheDocument()
    for (const label of ["All", "Park", "Garden", "Library", "Museum"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument()
    }
  })

  it("keeps category controls visible while refuges load", () => {
    renderControls({ loading: true, hasSearched: false })

    expect(screen.getByRole("button", { name: "Park" })).toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent("Finding quiet spaces…")
  })

  it("shows an inline refuge error and retries only the refuge search", async () => {
    const onRetry = vi.fn()
    const user = userEvent.setup()
    renderControls({ error: "Refuges timed out.", onRetry })

    expect(screen.getByRole("alert")).toHaveTextContent("Refuges timed out.")
    await user.click(screen.getByRole("button", { name: "Retry" }))

    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it("reports the total when every category is active", () => {
    renderControls()

    expect(screen.getByRole("status")).toHaveTextContent("2 quiet spaces found")
  })

  it("keeps controls and reports an active category with no matching refuges", () => {
    renderControls({ activeFilter: "GARDEN", filteredRefuges: [] })

    expect(screen.getByRole("button", { name: "Garden" })).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByRole("status")).toHaveTextContent("No quiet spaces match Garden")
  })

  it("reports matching refuges after a category filter", () => {
    renderControls({ activeFilter: "PARK", filteredRefuges: [park] })

    expect(screen.getByRole("status")).toHaveTextContent("1 quiet space found")
  })
})
