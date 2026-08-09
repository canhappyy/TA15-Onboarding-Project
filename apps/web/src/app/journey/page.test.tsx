import { cleanup, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { LocationSuggestion, Route } from "@clearway/shared"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import JourneyPage from "@/app/journey/page"
import { searchLocations } from "@/lib/location-search-api"
import { RouteSearchApiError, searchRoutes } from "@/lib/route-search-api"

vi.mock("@/lib/location-search-api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/location-search-api")>()
  return { ...original, searchLocations: vi.fn() }
})

vi.mock("@/lib/route-search-api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/route-search-api")>()
  return { ...original, searchRoutes: vi.fn() }
})

const locations: Record<string, LocationSuggestion> = {
  "Town Hall": {
    id: "town-hall",
    label: "Town Hall, Melbourne VIC",
    coordinates: { latitude: -37.8136, longitude: 144.9631 },
  },
  "State Library": {
    id: "state-library",
    label: "State Library, Melbourne VIC",
    coordinates: { latitude: -37.8098, longitude: 144.9652 },
  },
  Parliament: {
    id: "parliament",
    label: "Parliament, Melbourne VIC",
    coordinates: { latitude: -37.811, longitude: 144.9737 },
  },
}

const lowRoute: Route = {
  id: "low-route",
  durationMinutes: 12,
  walkingDistanceKm: 0.8,
  score: 0.91,
  indicator: "LOW",
  geometry: {
    type: "LineString",
    coordinates: [[144.9631, -37.8136]],
  },
  recommended: true,
  warning: null,
  explanation: "Lower sensory load.",
  freshness: {
    observedAt: "2026-08-09T10:00:00.000Z",
    stale: false,
    fallbackUsed: false,
  },
}

const highRoute: Route = {
  ...lowRoute,
  id: "high-route",
  durationMinutes: 9,
  walkingDistanceKm: 0.7,
  indicator: "HIGH",
  score: 0.52,
  recommended: false,
  warning: "Crowds may be intense.",
  explanation: "Higher sensory load.",
}

const mockedSearchLocations = vi.mocked(searchLocations)
const mockedSearchRoutes = vi.mocked(searchRoutes)

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })

  return { promise, resolve }
}

async function selectLocation(
  user: ReturnType<typeof userEvent.setup>,
  label: "Origin" | "Destination",
  query: keyof typeof locations
) {
  const input = screen.getByRole("combobox", { name: label })
  await user.clear(input)
  await user.type(input, query)
  await screen.findByRole("option", { name: locations[query].label })
  await user.keyboard("{ArrowDown}{Enter}")
}

async function selectLocations(user: ReturnType<typeof userEvent.setup>) {
  await selectLocation(user, "Origin", "Town Hall")
  await selectLocation(user, "Destination", "State Library")
}

beforeEach(() => {
  mockedSearchLocations.mockReset()
  mockedSearchLocations.mockImplementation(async (query) => [locations[query]])
  mockedSearchRoutes.mockReset()
})

afterEach(cleanup)

describe("JourneyPage", () => {
  it("disables search until locations are selected and shows searching while routes load", async () => {
    const pending = deferred<Route[]>()
    mockedSearchRoutes.mockReturnValueOnce(pending.promise)
    const user = userEvent.setup()
    render(<JourneyPage />)

    const searchButton = screen.getByRole("button", { name: "Search routes" })
    expect(searchButton).toBeDisabled()

    await selectLocations(user)
    expect(searchButton).toBeEnabled()
    await user.click(searchButton)

    expect(screen.getByRole("button", { name: "Searching…" })).toBeDisabled()
    expect(screen.getByRole("status")).toHaveTextContent("Searching routes…")

    pending.resolve([lowRoute])
    await screen.findByText("Lower sensory load.")
  })

  it("renders live route fields and no route link after a successful search", async () => {
    mockedSearchRoutes.mockResolvedValueOnce([lowRoute, highRoute])
    const user = userEvent.setup()
    render(<JourneyPage />)

    await selectLocations(user)
    await user.click(screen.getByRole("button", { name: "Search routes" }))

    expect(await screen.findByRole("status")).toHaveTextContent("2 routes found")
    expect(screen.getByText("12 min")).toBeInTheDocument()
    expect(screen.getByText("0.8 km")).toBeInTheDocument()
    expect(screen.getByText("LOW")).toBeInTheDocument()
    expect(screen.getByText("Recommended")).toBeInTheDocument()
    expect(screen.getByText("Lower sensory load.")).toBeInTheDocument()
    expect(screen.getByText("Crowds may be intense.")).toBeInTheDocument()
    for (const routeArticle of screen.getAllByRole("article")) {
      expect(within(routeArticle).queryByRole("link")).not.toBeInTheDocument()
    }
  })

  it("shows an empty route message after a successful search with no routes", async () => {
    mockedSearchRoutes.mockResolvedValueOnce([])
    const user = userEvent.setup()
    render(<JourneyPage />)

    await selectLocations(user)
    await user.click(screen.getByRole("button", { name: "Search routes" }))

    expect(await screen.findByText("No routes found for this journey.")).toBeInTheDocument()
  })

  it("filters successful routes by LOW and HIGH indicators", async () => {
    mockedSearchRoutes.mockResolvedValueOnce([lowRoute, highRoute])
    const user = userEvent.setup()
    render(<JourneyPage />)

    await selectLocations(user)
    await user.click(screen.getByRole("button", { name: "Search routes" }))
    await screen.findByText("Higher sensory load.")

    const lowFilter = screen.getByRole("button", { name: "Low" })
    const highFilter = screen.getByRole("button", { name: "High" })
    expect(lowFilter).toHaveAttribute("aria-pressed", "false")
    expect(highFilter).toHaveAttribute("aria-pressed", "false")

    await user.click(lowFilter)
    expect(lowFilter).toHaveAttribute("aria-pressed", "true")
    expect(highFilter).toHaveAttribute("aria-pressed", "false")
    expect(screen.getByText("Lower sensory load.")).toBeInTheDocument()
    expect(screen.queryByText("Higher sensory load.")).not.toBeInTheDocument()

    await user.click(lowFilter)
    expect(lowFilter).toHaveAttribute("aria-pressed", "false")

    await user.click(highFilter)
    expect(lowFilter).toHaveAttribute("aria-pressed", "false")
    expect(highFilter).toHaveAttribute("aria-pressed", "true")
    expect(screen.queryByText("Lower sensory load.")).not.toBeInTheDocument()
    expect(screen.getByText("Higher sensory load.")).toBeInTheDocument()
  })

  it("keeps filters available when the active filter has zero matches", async () => {
    mockedSearchRoutes.mockResolvedValueOnce([lowRoute])
    const user = userEvent.setup()
    render(<JourneyPage />)

    await selectLocations(user)
    await user.click(screen.getByRole("button", { name: "Search routes" }))
    await screen.findByText("Lower sensory load.")

    await user.click(screen.getByRole("button", { name: "High" }))
    expect(screen.getByRole("button", { name: "High" })).toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent("0 routes found")

    await user.click(screen.getByRole("button", { name: "High" }))
    expect(screen.getByText("Lower sensory load.")).toBeInTheDocument()
  })

  it("shows an inline route error and retries the search", async () => {
    mockedSearchRoutes
      .mockRejectedValueOnce(
        new RouteSearchApiError("UPSTREAM_TIMEOUT", "Route search timed out.")
      )
      .mockResolvedValueOnce([lowRoute])
    const user = userEvent.setup()
    render(<JourneyPage />)

    await selectLocations(user)
    await user.click(screen.getByRole("button", { name: "Search routes" }))

    expect(await screen.findByRole("alert")).toHaveTextContent("Route search timed out.")
    await user.click(screen.getByRole("button", { name: "Retry" }))
    expect(await screen.findByText("Lower sensory load.")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("clears completed results when a selected location changes", async () => {
    mockedSearchRoutes.mockResolvedValueOnce([lowRoute])
    const user = userEvent.setup()
    render(<JourneyPage />)

    await selectLocations(user)
    await user.click(screen.getByRole("button", { name: "Search routes" }))
    await screen.findByText("Lower sensory load.")

    await selectLocation(user, "Origin", "Parliament")

    expect(screen.getByText("Choose an origin and destination to view routes.")).toBeInTheDocument()
    expect(screen.queryByText("Lower sensory load.")).not.toBeInTheDocument()
  })
})
