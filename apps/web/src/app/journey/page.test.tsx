import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import JourneyPage from "@/app/journey/page"

vi.mock("@/lib/location-search-api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/location-search-api")>()
  return {
    ...original,
    searchLocations: vi.fn(async (text: string) => [
      {
        id: text.toLowerCase().replaceAll(" ", "-"),
        label: `${text}, Melbourne VIC`,
        coordinates: { latitude: -37.81, longitude: 144.96 },
      },
    ]),
  }
})

afterEach(cleanup)

describe("JourneyPage", () => {
  it("shows mock routes only after both locations are selected and searched", async () => {
    const user = userEvent.setup()
    render(<JourneyPage />)

    const searchButton = screen.getByRole("button", { name: "Search routes" })
    expect(searchButton).toBeDisabled()
    expect(screen.queryByText(/routes? found/i)).not.toBeInTheDocument()

    const origin = screen.getByRole("combobox", { name: "Origin" })
    await user.type(origin, "Town Hall")
    await screen.findByRole("option", { name: "Town Hall, Melbourne VIC" })
    await user.keyboard("{ArrowDown}{Enter}")

    const destination = screen.getByRole("combobox", { name: "Destination" })
    await user.type(destination, "State Library")
    await screen.findByRole("option", { name: "State Library, Melbourne VIC" })
    await user.keyboard("{ArrowDown}{Enter}")

    expect(searchButton).toBeEnabled()
    await user.click(searchButton)

    expect(screen.getByRole("status")).toHaveTextContent("3 routes found")
    expect(screen.getByText("Via Collins St")).toBeInTheDocument()
  })
})
