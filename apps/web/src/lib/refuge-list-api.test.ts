import { afterEach, describe, expect, it, vi } from "vitest"

import {
  RefugeListApiError,
  listRefuges,
} from "@/lib/refuge-list-api"

const request = {
  latitude: -37.8136,
  longitude: 144.9631,
  category: "GARDEN" as const,
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

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe("listRefuges", () => {
  it("gets the exact encoded refuge query from the configured API", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com///")
    const controller = new AbortController()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: { refuges: [refuge] } }),
    })
    vi.stubGlobal("fetch", fetchMock)

    await expect(listRefuges(request, { signal: controller.signal })).resolves.toEqual([
      refuge,
    ])

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/refuges?latitude=-37.8136&longitude=144.9631&category=GARDEN",
      { headers: { Accept: "application/json" }, signal: controller.signal }
    )
  })

  it("omits the category query when absent", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: { refuges: [] } }),
    })
    vi.stubGlobal("fetch", fetchMock)

    await listRefuges({ latitude: -37.8136, longitude: 144.9631 })

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/refuges?latitude=-37.8136&longitude=144.9631",
      { headers: { Accept: "application/json" }, signal: undefined }
    )
  })

  it("preserves API failure code and message", async () => {
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

    await expect(listRefuges(request)).rejects.toEqual(
      new RefugeListApiError("OUTSIDE_SERVICE_AREA", "Outside area.")
    )
  })

  it("reports missing public API configuration", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "")

    await expect(listRefuges(request)).rejects.toEqual(
      new RefugeListApiError(
        "CONFIGURATION_ERROR",
        "Quiet spaces are not configured."
      )
    )
  })

  it("converts fetch failures to a network error", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")))

    await expect(listRefuges(request)).rejects.toEqual(
      new RefugeListApiError(
        "NETWORK_ERROR",
        "Quiet spaces are unavailable. Try again."
      )
    )
  })

  it.each([
    { success: true, data: { refuges: undefined } },
    { success: true, data: {} },
    { data: { refuges: [] } },
  ])("rejects malformed response %o", async (payload) => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => payload })
    )

    await expect(listRefuges(request)).rejects.toEqual(
      new RefugeListApiError(
        "MALFORMED_RESPONSE",
        "Quiet spaces returned an invalid response."
      )
    )
  })

  it.each([
    ["null item", null],
    ["blank id", { ...refuge, id: "" }],
    ["non-string name", { ...refuge, name: 42 }],
    ["unknown category", { ...refuge, category: "CAFE" }],
    [
      "latitude outside its range",
      { ...refuge, coordinates: { latitude: -91, longitude: 144.9681 } },
    ],
    [
      "longitude outside its range",
      { ...refuge, coordinates: { latitude: -37.8146, longitude: 181 } },
    ],
    ["negative distance", { ...refuge, walkingDistanceKm: -0.1 }],
    ["missing source metadata", { ...refuge, metadata: {} }],
    [
      "non-string metadata value",
      { ...refuge, metadata: { source: "City of Melbourne Open Data", rank: 1 } },
    ],
    ["unsafe navigation URL", { ...refuge, navigationUrl: "javascript:alert(1)" }],
  ])("rejects a malformed refuge: %s", async (_name, malformedRefuge) => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { refuges: [malformedRefuge] } }),
      })
    )

    await expect(listRefuges(request)).rejects.toEqual(
      new RefugeListApiError(
        "MALFORMED_RESPONSE",
        "Quiet spaces returned an invalid response."
      )
    )
  })

  it("rethrows abort errors unchanged", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
    const abortError = new DOMException("Aborted", "AbortError")
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError))

    await expect(listRefuges(request)).rejects.toBe(abortError)
  })
})
