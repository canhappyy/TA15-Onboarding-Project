import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { Refuge } from "@clearway/shared"
import QuietSpacesPage from "@/app/quiet-spaces/page"
import { listRefuges } from "@/lib/refuge-list-api"

vi.mock("@/lib/refuge-list-api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/refuge-list-api")>()
  return { ...original, listRefuges: vi.fn() }
})

vi.mock("@/components/map/map", () => ({
  Map: ({ refuges }: { refuges: Refuge[] }) => (
    <div data-testid="quiet-spaces-map">
      {refuges.map((refuge) => (
        <span key={refuge.id}>{refuge.name} marker</span>
      ))}
    </div>
  ),
}))

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
  walkingDistanceKm: 0.8,
  navigationUrl: "https://maps.example/museum",
}

const mockedListRefuges = vi.mocked(listRefuges)

function installGeolocation() {
  let onSuccess: PositionCallback | undefined
  let onError: PositionErrorCallback | undefined
  Object.defineProperty(window.navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: vi.fn((success: PositionCallback, error?: PositionErrorCallback) => {
        onSuccess = success
        onError = error
      }),
    },
  })

  return {
    succeed() {
      onSuccess?.({
        coords: { latitude: -37.8136, longitude: 144.9631 },
      } as GeolocationPosition)
    },
    deny() {
      onError?.({ message: "Location permission denied" } as GeolocationPositionError)
    },
  }
}

beforeEach(() => {
  mockedListRefuges.mockReset()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe("QuietSpacesPage", () => {
  it("shows locating then real refuge cards and matching map markers", async () => {
    const geolocation = installGeolocation()
    mockedListRefuges.mockResolvedValue([park, museum])
    render(<QuietSpacesPage />)

    expect(screen.getByRole("status")).toHaveTextContent("Locating your position")
    geolocation.succeed()

    expect(await screen.findByText("Treasury Gardens")).toBeInTheDocument()
    expect(
      screen.getByText((_, element) => element?.textContent === "PARK · 0.6 km away")
    ).toBeInTheDocument()
    expect(screen.getAllByText("City of Melbourne Open Data")).toHaveLength(2)
    expect(screen.getByText("Melbourne Museum marker")).toBeInTheDocument()
    expect(screen.getAllByRole("link")[0]).toHaveAttribute("target", "_blank")
    expect(screen.getAllByRole("link")[0]).toHaveAttribute("rel", expect.stringContaining("noopener"))
    expect(screen.getAllByRole("link")[0]).toHaveAttribute("rel", expect.stringContaining("noreferrer"))
  })

  it("filters both cards and map markers and retains zero-result filters", async () => {
    const geolocation = installGeolocation()
    mockedListRefuges.mockResolvedValue([park, museum])
    const user = userEvent.setup()
    render(<QuietSpacesPage />)
    geolocation.succeed()
    await screen.findByText("Treasury Gardens")

    await user.click(screen.getByRole("button", { name: "Museum" }))
    expect(screen.queryByText("Treasury Gardens")).not.toBeInTheDocument()
    expect(screen.getByText("Melbourne Museum")).toBeInTheDocument()
    expect(screen.queryByText("Treasury Gardens marker")).not.toBeInTheDocument()
    expect(screen.getByText("Melbourne Museum marker")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Garden" }))
    expect(screen.getByRole("button", { name: "Garden" })).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByRole("status")).toHaveTextContent("No quiet spaces match Garden")
    expect(screen.getByRole("button", { name: "Museum" })).toBeInTheDocument()
    expect(screen.queryByText(/Caf[eé]/i)).not.toBeInTheDocument()
  })

  it("offers the CBD fallback after geolocation denial", async () => {
    const geolocation = installGeolocation()
    mockedListRefuges.mockResolvedValue([park])
    const user = userEvent.setup()
    render(<QuietSpacesPage />)
    geolocation.deny()

    expect(await screen.findByRole("alert")).toHaveTextContent("Location permission denied")
    await user.click(screen.getByRole("button", { name: "Use Melbourne CBD" }))

    expect(await screen.findByText("Treasury Gardens")).toBeInTheDocument()
    expect(screen.getByText("Using Melbourne CBD as your location.")).toBeInTheDocument()
  })

  it("shows request failures with a retry action", async () => {
    const geolocation = installGeolocation()
    mockedListRefuges
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce([park])
    const user = userEvent.setup()
    render(<QuietSpacesPage />)
    geolocation.succeed()

    expect(await screen.findByRole("alert")).toHaveTextContent("Quiet spaces are unavailable")
    await user.click(screen.getByRole("button", { name: "Retry" }))
    expect(await screen.findByText("Treasury Gardens")).toBeInTheDocument()
  })
})
