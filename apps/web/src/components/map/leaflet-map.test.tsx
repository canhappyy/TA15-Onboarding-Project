import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import type { Refuge } from "@clearway/shared"

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null,
  CircleMarker: ({ children, center }: { children: React.ReactNode; center: [number, number] }) => (
    <div data-testid="refuge-marker" data-center={center.join(",")}>
      {children}
    </div>
  ),
  Popup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useMap: () => ({ getZoom: () => 13, setView: vi.fn() }),
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
    const link = screen.getByRole("link", { name: "Navigate to Treasury Gardens" })
    expect(link).toHaveAttribute("href", refuge.navigationUrl)
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", "noopener noreferrer")
  })
})
