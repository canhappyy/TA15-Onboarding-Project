import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { Route } from "@clearway/shared"
import { afterEach, describe, expect, it, vi } from "vitest"

import { RouteCard } from "@/components/journey/route-card"

const route: Route = {
  id: "route-1",
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
  warning: "Pedestrian data may be stale.",
  explanation:
    "Calculated using pedestrian crowd information and nearby refuge availability.",
  freshness: {
    observedAt: "2026-08-09T10:00:00.000Z",
    stale: true,
    fallbackUsed: false,
  },
}

afterEach(cleanup)

describe("RouteCard", () => {
  it("exposes selection state and selects the route from its summary", async () => {
    const onSelect = vi.fn()
    const user = userEvent.setup()

    render(
      <RouteCard route={route} selected={false} onSelect={onSelect} />
    )

    const button = screen.getByRole("button", {
      name: "Select 12 minute LOW sensory route",
    })
    expect(button).toHaveAttribute("aria-pressed", "false")
    expect(button).toHaveAttribute("aria-expanded", "false")
    expect(screen.queryByText("Selected route")).not.toBeInTheDocument()

    await user.click(button)

    expect(onSelect).toHaveBeenCalledWith("route-1")
  })

  it("shows selected route details and an explicit score explanation disclosure", async () => {
    const user = userEvent.setup()

    render(
      <RouteCard route={route} selected onSelect={() => undefined} />
    )

    const button = screen.getByRole("button", {
      name: "Selected 12 minute LOW sensory route",
    })
    expect(button).toHaveAttribute("aria-pressed", "true")
    expect(button).toHaveAttribute("aria-expanded", "true")
    expect(screen.getByText("Selected route")).toBeInTheDocument()
    expect(screen.getByText("Sensory score 15")).toBeInTheDocument()
    expect(screen.getByText("Pedestrian data may be stale.")).toBeInTheDocument()
    expect(screen.getByText("Data status: Pedestrian data may be stale")).toBeInTheDocument()

    await user.click(
      screen.getByText("How is this sensory score calculated?")
    )

    expect(screen.getByText(route.explanation)).toBeInTheDocument()
  })
})
