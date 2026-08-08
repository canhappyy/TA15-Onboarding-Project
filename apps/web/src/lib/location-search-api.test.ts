import { afterEach, describe, expect, it, vi } from "vitest"

import {
  LocationSearchApiError,
  searchLocations,
} from "@/lib/location-search-api"


afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})


describe("searchLocations", () => {
  it("requests encoded suggestions from the configured API", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com/")
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          suggestions: [
            {
              id: "venue.123",
              label: "State Library Victoria, Melbourne VIC",
              coordinates: { latitude: -37.8098, longitude: 144.9652 },
            },
          ],
        },
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const suggestions = await searchLocations("State Library & Swanston")

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/locations/search?text=State+Library+%26+Swanston",
      expect.objectContaining({ headers: { Accept: "application/json" } })
    )
    expect(suggestions[0].id).toBe("venue.123")
  })

  it("preserves API error code and message", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({
          success: false,
          error: {
            code: "OUTSIDE_SERVICE_AREA",
            message: "No matching locations were found within the City of Melbourne.",
          },
        }),
      })
    )

    await expect(searchLocations("Richmond")).rejects.toEqual(
      new LocationSearchApiError(
        "OUTSIDE_SERVICE_AREA",
        "No matching locations were found within the City of Melbourne."
      )
    )
  })

  it("reports missing public API configuration", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "")

    await expect(searchLocations("Library")).rejects.toMatchObject({
      code: "CONFIGURATION_ERROR",
    })
  })

  it("rejects a malformed upstream response", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: [] }),
      })
    )

    await expect(searchLocations("Library")).rejects.toMatchObject({
      code: "UPSTREAM_ERROR",
    })
  })
})
