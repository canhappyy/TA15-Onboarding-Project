import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { LocationSuggestion } from "@clearway/shared"
import { LocationAutocomplete } from "@/components/journey/location-autocomplete"
import { LocationSearchApiError } from "@/lib/location-search-api"


const suggestion: LocationSuggestion = {
  id: "venue.123",
  label: "State Library Victoria, Melbourne VIC",
  coordinates: { latitude: -37.8098, longitude: 144.9652 },
}


afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})


describe("LocationAutocomplete", () => {
  it("selects a suggestion using the keyboard", async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    const search = vi.fn().mockResolvedValue([suggestion])

    render(
      <LocationAutocomplete
        id="destination"
        label="Destination"
        placeholder="Search destination"
        selected={null}
        onSelect={onSelect}
        search={search}
        debounceMs={0}
      />
    )

    const input = screen.getByRole("combobox", { name: "Destination" })
    await user.type(input, "State Library")
    await screen.findByRole("option", { name: suggestion.label })
    await user.keyboard("{ArrowDown}{Enter}")

    expect(onSelect).toHaveBeenCalledWith(suggestion)
    expect(input).toHaveValue(suggestion.label)
  })

  it("shows loading then an empty state", async () => {
    const user = userEvent.setup()
    let resolveSearch: (results: LocationSuggestion[]) => void = () => undefined
    const search = vi.fn().mockImplementation(
      () => new Promise<LocationSuggestion[]>((resolve) => { resolveSearch = resolve })
    )

    render(
      <LocationAutocomplete
        id="destination"
        label="Destination"
        placeholder="Search destination"
        selected={null}
        onSelect={vi.fn()}
        search={search}
        debounceMs={0}
      />
    )

    await user.type(screen.getByRole("combobox"), "Unknown")
    expect(await screen.findByRole("status")).toHaveTextContent("Searching")
    resolveSearch([])

    expect(await screen.findByText("No matching locations found.")).toBeInTheDocument()
  })

  it("shows an outside-area error and retries", async () => {
    const user = userEvent.setup()
    const search = vi
      .fn()
      .mockRejectedValueOnce(
        new LocationSearchApiError(
          "OUTSIDE_SERVICE_AREA",
          "No matching locations were found within the City of Melbourne."
        )
      )
      .mockResolvedValueOnce([suggestion])

    render(
      <LocationAutocomplete
        id="origin"
        label="Origin"
        placeholder="Search origin"
        selected={null}
        onSelect={vi.fn()}
        search={search}
        debounceMs={0}
      />
    )

    await user.type(screen.getByRole("combobox"), "Richmond")
    expect(await screen.findByRole("alert")).toHaveTextContent("within the City of Melbourne")
    await user.click(screen.getByRole("button", { name: "Retry location search" }))

    expect(await screen.findByRole("option", { name: suggestion.label })).toBeInTheDocument()
    expect(search).toHaveBeenCalledTimes(2)
  })

  it("keeps manual origin search available when geolocation is denied", async () => {
    const user = userEvent.setup()
    const getCurrentPosition = vi.fn((_success, error) => {
      error({ code: 1, message: "User denied Geolocation" })
    })
    Object.defineProperty(window.navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition },
    })

    render(
      <LocationAutocomplete
        id="origin"
        label="Origin"
        placeholder="Search origin"
        selected={null}
        onSelect={vi.fn()}
        allowCurrentLocation
        search={vi.fn().mockResolvedValue([])}
        debounceMs={0}
      />
    )

    await user.click(screen.getByRole("button", { name: "Use current location" }))

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Location permission was denied. Enter an origin manually."
    )
    expect(screen.getByRole("combobox", { name: "Origin" })).toBeEnabled()
    await user.type(screen.getByRole("combobox"), "Library")
    await waitFor(() => expect(getCurrentPosition).toHaveBeenCalledOnce())
  })
})
