import { afterEach, describe, expect, it, vi } from "vitest"

import {
  RouteSearchApiError,
  searchRoutes,
} from "@/lib/route-search-api"

const route = {
  id: "route.123",
  durationMinutes: 12,
  walkingDistanceKm: 0.8,
  score: 0.91,
  indicator: "LOW" as const,
  geometry: {
    type: "LineString" as const,
    coordinates: [[144.9631, -37.8136]],
  },
  recommended: true,
  warning: null,
  explanation: "Lowest sensory score.",
  freshness: {
    observedAt: "2026-08-09T10:00:00.000Z",
    stale: false,
    fallbackUsed: false,
  },
}

const alternativeRoute = { ...route, id: "route.456", score: 0.67 }

const request = {
  origin: { latitude: -37.8136, longitude: 144.9631 },
  destination: { latitude: -37.8098, longitude: 144.9652 },
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe("searchRoutes", () => {
  it("posts the exact request body to the configured route endpoint", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com///")
    const controller = new AbortController()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: { routes: [route, alternativeRoute] },
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    await expect(searchRoutes(request, { signal: controller.signal })).resolves.toEqual(
      [route, alternativeRoute]
    )

    expect(fetchMock).toHaveBeenCalledWith("https://api.example.com/routes/search", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
      signal: controller.signal,
    })
  })

  it("preserves an API failure code and message", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({
          success: false,
          error: { code: "OUTSIDE_SERVICE_AREA", message: "Outside service area." },
        }),
      })
    )

    await expect(searchRoutes(request)).rejects.toEqual(
      new RouteSearchApiError("OUTSIDE_SERVICE_AREA", "Outside service area.")
    )
  })

  it("rejects when the public API base URL is absent", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "")

    await expect(searchRoutes(request)).rejects.toEqual(
      new RouteSearchApiError(
        "CONFIGURATION_ERROR",
        "Route search is not configured."
      )
    )
  })

  it("converts fetch failures to a network error", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")))

    await expect(searchRoutes(request)).rejects.toEqual(
      new RouteSearchApiError(
        "NETWORK_ERROR",
        "Route search is unavailable. Try again."
      )
    )
  })

  it("rejects malformed JSON", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => {
          throw new SyntaxError("Unexpected token")
        },
      })
    )

    await expect(searchRoutes(request)).rejects.toMatchObject({
      code: "UPSTREAM_ERROR",
      message: "Route search returned an invalid response.",
    })
  })

  it("rejects malformed response envelopes", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: {} }) })
    )

    await expect(searchRoutes(request)).rejects.toMatchObject({
      code: "UPSTREAM_ERROR",
    })
  })

  it("rejects success envelopes on non-success HTTP responses", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ success: true, data: { routes: [route] } }),
      })
    )

    await expect(searchRoutes(request)).rejects.toMatchObject({
      code: "UPSTREAM_ERROR",
    })
  })

  it.each([undefined, {}])("rejects success responses with routes %o", async (routes) => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { routes } }),
      })
    )

    await expect(searchRoutes(request)).rejects.toMatchObject({
      code: "UPSTREAM_ERROR",
    })
  })

  it("rethrows abort errors unchanged", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    const abortError = new DOMException("Aborted", "AbortError")
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError))

    await expect(searchRoutes(request)).rejects.toBe(abortError)
  })
})
