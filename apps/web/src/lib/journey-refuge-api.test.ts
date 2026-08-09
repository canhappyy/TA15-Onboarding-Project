import { afterEach, describe, expect, it, vi } from "vitest"

import type { RefugeSearchRequest } from "@clearway/shared"

import {
  JourneyRefugeSearchApiError,
  searchJourneyRefuges,
} from "@/lib/journey-refuge-api"

const request: RefugeSearchRequest = {
  origin: { latitude: -37.8136, longitude: 144.9631 },
  route: {
    type: "LineString" as const,
    coordinates: [
      [144.9631, -37.8136],
      [144.9681, -37.8146],
    ],
  },
  categories: ["GARDEN", "LIBRARY"] as const,
}

const refuge = {
  id: "landmark.123",
  name: "Treasury Gardens",
  category: "GARDEN" as const,
  coordinates: { latitude: -37.8146, longitude: 144.9681 },
  walkingDistanceKm: 0.6,
  metadata: { source: "City of Melbourne Open Data" },
  navigationUrl: "https://www.google.com/maps/dir/?api=1",
}

const secondRefuge = {
  ...refuge,
  id: "library.456",
  name: "City Library",
  category: "LIBRARY" as const,
  walkingDistanceKm: 1.1,
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe("searchJourneyRefuges", () => {
  it("posts the exact journey request and preserves refuge order", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com///")
    const controller = new AbortController()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: { refuges: [secondRefuge, refuge] } }),
    })
    vi.stubGlobal("fetch", fetchMock)

    await expect(
      searchJourneyRefuges(request, { signal: controller.signal })
    ).resolves.toEqual([secondRefuge, refuge])

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/refuges/search",
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
        signal: controller.signal,
      }
    )
  })

  it("preserves backend failure code and message", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({
          success: false,
          error: { code: "OUTSIDE_SERVICE_AREA", message: "Outside area." },
        }),
      })
    )

    await expect(searchJourneyRefuges(request)).rejects.toEqual(
      new JourneyRefugeSearchApiError("OUTSIDE_SERVICE_AREA", "Outside area.")
    )
  })

  it("reports missing public API configuration", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "")

    await expect(searchJourneyRefuges(request)).rejects.toEqual(
      new JourneyRefugeSearchApiError(
        "CONFIGURATION_ERROR",
        "Journey quiet spaces are not configured."
      )
    )
  })

  it("converts fetch failure to a network error", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")))

    await expect(searchJourneyRefuges(request)).rejects.toEqual(
      new JourneyRefugeSearchApiError(
        "NETWORK_ERROR",
        "Journey quiet spaces are unavailable. Try again."
      )
    )
  })

  it.each([
    ["malformed JSON", undefined, new SyntaxError("invalid JSON")],
    ["malformed envelope", { data: { refuges: [] } }, undefined],
    ["malformed refuge item", { success: true, data: { refuges: [{ ...refuge, id: "" }] } }, undefined],
  ])("rejects %s", async (_name, payload, jsonError) => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => {
          if (jsonError) throw jsonError
          return payload
        },
      })
    )

    await expect(searchJourneyRefuges(request)).rejects.toEqual(
      new JourneyRefugeSearchApiError(
        "MALFORMED_RESPONSE",
        "Journey quiet spaces returned an invalid response."
      )
    )
  })

  it("rejects a success envelope received with a non-2xx response", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ success: true, data: { refuges: [] } }),
      })
    )

    await expect(searchJourneyRefuges(request)).rejects.toEqual(
      new JourneyRefugeSearchApiError(
        "MALFORMED_RESPONSE",
        "Journey quiet spaces returned an invalid response."
      )
    )
  })

  it("rethrows abort errors unchanged", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    const abortError = new DOMException("Aborted", "AbortError")
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError))

    await expect(searchJourneyRefuges(request)).rejects.toBe(abortError)
  })
})
