import { act, renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import type { LocationSuggestion, Route } from "@clearway/shared"
import { RouteSearchApiError } from "@/lib/route-search-api"
import { type SearchRoutes, useJourney } from "@/hooks/use-journey"

const origin: LocationSuggestion = {
  id: "origin.1",
  label: "Town Hall",
  coordinates: { latitude: -37.8136, longitude: 144.9631 },
}

const updatedOrigin: LocationSuggestion = {
  id: "origin.2",
  label: "Parliament",
  coordinates: { latitude: -37.811, longitude: 144.9737 },
}

const destination: LocationSuggestion = {
  id: "destination.1",
  label: "State Library",
  coordinates: { latitude: -37.8098, longitude: 144.9652 },
}

const lowRoute: Route = {
  id: "low-route",
  durationMinutes: 12,
  walkingDistanceKm: 0.8,
  score: 0.91,
  indicator: "LOW",
  geometry: {
    type: "LineString",
    coordinates: [[144.9631, -37.8136]],
  },
  recommended: true,
  warning: null,
  explanation: "Lower sensory load.",
  freshness: {
    observedAt: "2026-08-09T10:00:00.000Z",
    stale: false,
    fallbackUsed: false,
  },
}

const highRoute: Route = {
  ...lowRoute,
  id: "high-route",
  indicator: "HIGH",
  score: 0.52,
}

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined
  let reject: (reason?: unknown) => void = () => undefined
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })

  return { promise, resolve, reject }
}

function selectLocations(
  result: { current: ReturnType<typeof useJourney> },
  selectedOrigin = origin
) {
  act(() => {
    result.current.setOrigin(selectedOrigin)
    result.current.setDestination(destination)
  })
}

describe("useJourney", () => {
  it("stores successful routes in response order", async () => {
    const search: SearchRoutes = async () => [highRoute, lowRoute]
    const { result } = renderHook(() => useJourney(search))

    selectLocations(result)
    await act(async () => {
      await result.current.searchJourney()
    })

    expect(result.current.hasSearched).toBe(true)
    expect(result.current.routes).toEqual([highRoute, lowRoute])
    expect(result.current.filteredRoutes).toEqual([highRoute, lowRoute])
  })

  it("disables search while a request is loading", async () => {
    const pending = deferred<Route[]>()
    const search: SearchRoutes = () => pending.promise
    const { result } = renderHook(() => useJourney(search))

    selectLocations(result)
    expect(result.current.canSearch).toBe(true)

    act(() => {
      void result.current.searchJourney()
    })

    expect(result.current.loading).toBe(true)
    expect(result.current.canSearch).toBe(false)

    await act(async () => {
      pending.resolve([lowRoute])
      await pending.promise
    })

    expect(result.current.loading).toBe(false)
    expect(result.current.canSearch).toBe(true)
  })

  it("filters LOW and HIGH routes without changing response order", async () => {
    const search: SearchRoutes = async () => [highRoute, lowRoute, highRoute]
    const { result } = renderHook(() => useJourney(search))

    selectLocations(result)
    await act(async () => {
      await result.current.searchJourney()
    })

    act(() => {
      result.current.toggleFilter("LOW")
    })
    expect(result.current.filteredRoutes).toEqual([lowRoute])

    act(() => {
      result.current.toggleFilter("HIGH")
    })
    expect(result.current.filteredRoutes).toEqual([highRoute, highRoute])

    act(() => {
      result.current.toggleFilter("HIGH")
    })
    expect(result.current.activeFilter).toBe("all")
    expect(result.current.filteredRoutes).toEqual([highRoute, lowRoute, highRoute])
  })

  it("exposes route API error messages after a completed failure", async () => {
    const search: SearchRoutes = async () => {
      throw new RouteSearchApiError("OUTSIDE_SERVICE_AREA", "Outside service area.")
    }
    const { result } = renderHook(() => useJourney(search))

    selectLocations(result)
    await act(async () => {
      await result.current.searchJourney()
    })

    expect(result.current.routes).toEqual([])
    expect(result.current.error).toBe("Outside service area.")
    expect(result.current.hasSearched).toBe(true)
    expect(result.current.loading).toBe(false)
  })

  it("uses the unavailable message for unknown failures", async () => {
    const search: SearchRoutes = async () => {
      throw new Error("offline")
    }
    const { result } = renderHook(() => useJourney(search))

    selectLocations(result)
    await act(async () => {
      await result.current.searchJourney()
    })

    expect(result.current.error).toBe("Route search is unavailable. Try again.")
    expect(result.current.hasSearched).toBe(true)
  })

  it("retries using the current location coordinates", async () => {
    let attempt = 0
    const search: SearchRoutes = async (request) => {
      attempt += 1
      if (attempt === 1) {
        throw new RouteSearchApiError("UPSTREAM_TIMEOUT", "Timed out.")
      }
      if (request.origin.latitude !== updatedOrigin.coordinates.latitude) {
        throw new Error("stale origin")
      }
      return [lowRoute]
    }
    const { result } = renderHook(() => useJourney(search))

    selectLocations(result, updatedOrigin)
    await act(async () => {
      await result.current.searchJourney()
    })
    expect(result.current.error).toBe("Timed out.")

    await act(async () => {
      await result.current.retrySearch()
    })

    expect(result.current.error).toBeNull()
    expect(result.current.routes).toEqual([lowRoute])
    expect(result.current.hasSearched).toBe(true)
  })

  it("clears completed results and errors when a location changes", async () => {
    const search: SearchRoutes = async () => {
      throw new RouteSearchApiError("UPSTREAM_ERROR", "Route service failed.")
    }
    const { result } = renderHook(() => useJourney(search))

    selectLocations(result)
    await act(async () => {
      await result.current.searchJourney()
    })
    act(() => {
      result.current.toggleFilter("HIGH")
      result.current.setOrigin(updatedOrigin)
    })

    expect(result.current.routes).toEqual([])
    expect(result.current.error).toBeNull()
    expect(result.current.hasSearched).toBe(false)
    expect(result.current.activeFilter).toBe("all")
  })

  it("aborts an active request before starting the next one", async () => {
    const first = deferred<Route[]>()
    const second = deferred<Route[]>()
    const signals: AbortSignal[] = []
    let searchIndex = 0
    const search: SearchRoutes = (_request, options) => {
      if (options?.signal) signals.push(options.signal)
      return [first, second][searchIndex++].promise
    }
    const { result } = renderHook(() => useJourney(search))

    selectLocations(result)
    act(() => {
      void result.current.searchJourney()
      void result.current.searchJourney()
    })

    expect(signals[0]?.aborted).toBe(true)

    await act(async () => {
      second.resolve([lowRoute])
      await second.promise
    })
    expect(result.current.routes).toEqual([lowRoute])
  })

  it("suppresses an aborted request that resolves after a newer search", async () => {
    const first = deferred<Route[]>()
    const second = deferred<Route[]>()
    let searchIndex = 0
    const search: SearchRoutes = () => [first, second][searchIndex++].promise
    const { result } = renderHook(() => useJourney(search))

    selectLocations(result)
    act(() => {
      void result.current.searchJourney()
      void result.current.searchJourney()
    })

    await act(async () => {
      first.resolve([highRoute])
      await first.promise
    })
    expect(result.current.routes).toEqual([])
    expect(result.current.loading).toBe(true)

    await act(async () => {
      second.resolve([lowRoute])
      await second.promise
    })
    expect(result.current.routes).toEqual([lowRoute])
    expect(result.current.loading).toBe(false)
  })
})
