import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { Refuge, Route } from "@clearway/shared"

const { fitBounds, setView } = vi.hoisted(() => ({
  fitBounds: vi.fn(),
  setView: vi.fn(),
}))

afterEach(() => {
  cleanup()
  fitBounds.mockClear()
  setView.mockClear()
})

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null,
  CircleMarker: ({ children, center, pathOptions }: { children: React.ReactNode; center: [number, number]; pathOptions: { color: string } }) => (
    <div
      data-testid={pathOptions.color === "#0f766e" ? "origin-marker" : pathOptions.color === "#b91c1c" ? "destination-marker" : "refuge-marker"}
      data-center={center.join(",")}
    >
      {children}
    </div>
  ),
  Polyline: ({ eventHandlers, pathOptions, positions }: { eventHandlers: { click: () => void }; pathOptions: { color: string; weight: number }; positions: [number, number][] }) => (
    <button
      type="button"
      data-testid="route-line"
      data-color={pathOptions.color}
      data-weight={pathOptions.weight}
      data-positions={JSON.stringify(positions)}
      onClick={eventHandlers.click}
    />
  ),
  Popup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useMap: () => ({ fitBounds, getZoom: () => 13, setView }),
}))

import { LeafletMap } from "@/components/map/leaflet-map"

const refuge: Refuge = {
  id: "park.1",
  name: "Treasury Gardens",
  category: "PARK",
  coordinates: { latitude: -37.8146, longitude: 144.9681 },
  walkingDistanceKm: 0.6,
  metadata: { source: "City of Melbourne Open Data" },
  navigationUrl: "https://maps.example/treasury",
}

const distantRefuge: Refuge = {
  ...refuge,
  id: "library.1",
  name: "Distant Library",
  category: "LIBRARY",
  coordinates: { latitude: -37.803, longitude: 144.978 },
}

const lowRoute: Route = {
  id: "route-low",
  durationMinutes: 12,
  walkingDistanceKm: 0.8,
  score: 15,
  indicator: "LOW",
  geometry: {
    type: "LineString",
    coordinates: [
      [144.9631, -37.8136],
      [144.9652, -37.8098],
    ],
  },
  recommended: true,
  warning: null,
  explanation: "Lower sensory load.",
  freshness: { observedAt: null, stale: false, fallbackUsed: false },
}

const highRoute: Route = {
  ...lowRoute,
  id: "route-high",
  indicator: "HIGH",
  recommended: false,
  geometry: {
    type: "LineString",
    coordinates: [
      [144.9631, -37.8136],
      [144.967, -37.811],
      [144.9652, -37.8098],
    ],
  },
}

describe("LeafletMap", () => {
  it("renders a marker and safe navigation popup for each refuge", () => {
    render(
      <LeafletMap
        origin={{ latitude: -37.8136, longitude: 144.9631 }}
        refuges={[refuge]}
      />
    )

    expect(screen.getByTestId("refuge-marker")).toHaveAttribute(
      "data-center",
      "-37.8146,144.9681"
    )
    expect(screen.getByText("Treasury Gardens")).toBeInTheDocument()
    expect(screen.getByText("Park")).toBeInTheDocument()
    expect(screen.getByText("0.6 km away")).toBeInTheDocument()
    const link = screen.getByRole("link", { name: "Navigate to Treasury Gardens" })
    expect(link).toHaveAttribute("href", refuge.navigationUrl)
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", "noopener noreferrer")
  })

  it("renders selectable routes, highlights selection, endpoints, and fits journey bounds", async () => {
    const onRouteSelect = vi.fn()
    const user = userEvent.setup()

    render(
      <LeafletMap
        origin={{ latitude: -37.8136, longitude: 144.9631 }}
        destination={{ latitude: -37.8098, longitude: 144.9652 }}
        routes={[lowRoute, highRoute]}
        selectedRouteId="route-low"
        onRouteSelect={onRouteSelect}
      />
    )

    const routeLines = screen.getAllByTestId("route-line")
    expect(routeLines).toHaveLength(2)
    expect(routeLines[0]).toHaveAttribute("data-color", "#94a3b8")
    expect(routeLines[0]).toHaveAttribute("data-weight", "4")
    expect(routeLines[1]).toHaveAttribute("data-color", "#475569")
    expect(routeLines[1]).toHaveAttribute("data-weight", "6")
    expect(screen.getByTestId("origin-marker")).toHaveAttribute(
      "data-center",
      "-37.8136,144.9631"
    )
    expect(screen.getByTestId("destination-marker")).toHaveAttribute(
      "data-center",
      "-37.8098,144.9652"
    )

    await user.click(routeLines[0])
    expect(onRouteSelect).toHaveBeenCalledWith("route-high")

    await waitFor(() => {
      expect(fitBounds).toHaveBeenCalledWith(
        [
          [-37.8136, 144.9631],
          [-37.8098, 144.9652],
          [-37.8136, 144.9631],
          [-37.811, 144.967],
          [-37.8098, 144.9652],
        ],
        { padding: [24, 24] }
      )
    })
  })

  it("fits journey bounds around route geometry and visible refuges", async () => {
    render(
      <LeafletMap
        origin={{ latitude: -37.8136, longitude: 144.9631 }}
        routes={[lowRoute]}
        refuges={[distantRefuge]}
        selectedRouteId="route-low"
      />
    )

    await waitFor(() => {
      expect(fitBounds).toHaveBeenCalledWith(
        [
          [-37.8136, 144.9631],
          [-37.8098, 144.9652],
          [-37.803, 144.978],
        ],
        { padding: [24, 24] }
      )
    })
  })

  it("keeps a route-less quiet-spaces map centered on its single origin", async () => {
    const origin = { latitude: -37.8136, longitude: 144.9631 }

    render(<LeafletMap origin={origin} refuges={[refuge, distantRefuge]} />)

    await waitFor(() => {
      expect(setView).toHaveBeenCalledWith(
        [origin.latitude, origin.longitude],
        13
      )
    })
    expect(fitBounds).not.toHaveBeenCalled()
  })
})
