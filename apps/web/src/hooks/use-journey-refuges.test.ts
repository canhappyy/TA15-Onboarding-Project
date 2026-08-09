import { StrictMode, createElement } from "react"
import { act, render, renderHook, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import type { Coordinates, Refuge, Route } from "@clearway/shared"
import { JourneyRefugeSearchApiError } from "@/lib/journey-refuge-api"
import {
  type SearchJourneyRefuges,
  useJourneyRefuges,
} from "@/hooks/use-journey-refuges"

const origin: Coordinates = { latitude: -37.8136, longitude: 144.9631 }

const route: Route = {
  id: "route.1",
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

const nextRoute: Route = {
  ...route,
  id: "route.2",
  geometry: {
    type: "LineString",
    coordinates: [[144.9701, -37.8136]],
  },
}

const park: Refuge = {
  id: "park.1",
  name: "Treasury Gardens",
  category: "PARK",
  coordinates: { latitude: -37.8146, longitude: 144.9681 },
  walkingDistanceKm: 0.6,
  metadata: { source: "City of Melbourne Open Data" },
  navigationUrl: "https://www.google.com/maps/dir/?api=1",
}

const garden: Refuge = {
  ...park,
  id: "garden.1",
  name: "Carlton Gardens",
  category: "GARDEN",
}

const library: Refuge = {
  ...park,
  id: "library.1",
  name: "State Library Victoria",
  category: "LIBRARY",
}

const museum: Refuge = {
  ...park,
  id: "museum.1",
  name: "Melbourne Museum",
  category: "MUSEUM",
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

function JourneyRefugesHarness({ search }: { search: SearchJourneyRefuges }) {
  const { refuges } = useJourneyRefuges(origin, route, search)
  return createElement("output", null, refuges.map((refuge) => refuge.name).join(","))
}

describe("useJourneyRefuges", () => {
  it("waits for both route inputs before searching", () => {
    const search: SearchJourneyRefuges = vi.fn().mockResolvedValue([])
    const { rerender } = renderHook(
      ({ currentOrigin, selectedRoute }) =>
        useJourneyRefuges(currentOrigin, selectedRoute, search),
      { initialProps: { currentOrigin: null as Coordinates | null, selectedRoute: null as Route | null } }
    )

    expect(search).not.toHaveBeenCalled()

    rerender({ currentOrigin: origin, selectedRoute: null })
    expect(search).not.toHaveBeenCalled()
  })

  it("stores a successful response in response order with All selected", async () => {
    const search: SearchJourneyRefuges = vi.fn().mockResolvedValue([museum, park, library])
    const { result } = renderHook(() => useJourneyRefuges(origin, route, search))

    await waitFor(() => expect(result.current.refuges).toEqual([museum, park, library]))

    expect(search).toHaveBeenCalledWith(
      { origin, route: route.geometry },
      { signal: expect.any(AbortSignal) }
    )
    expect(result.current.filteredRefuges).toEqual([museum, park, library])
    expect(result.current.activeFilter).toBe("all")
    expect(result.current.hasSearched).toBe(true)
  })

  it("filters all refuge categories locally", async () => {
    const search: SearchJourneyRefuges = vi.fn().mockResolvedValue([park, garden, library, museum])
    const { result } = renderHook(() => useJourneyRefuges(origin, route, search))

    await waitFor(() => expect(result.current.refuges).toEqual([park, garden, library, museum]))

    for (const [filter, refuge] of [
      ["PARK", park],
      ["GARDEN", garden],
      ["LIBRARY", library],
      ["MUSEUM", museum],
    ] as const) {
      act(() => {
        result.current.toggleFilter(filter)
      })
      expect(result.current.filteredRefuges).toEqual([refuge])
    }

    expect(search).toHaveBeenCalledTimes(1)
  })

  it("returns a repeated active filter to All", async () => {
    const search: SearchJourneyRefuges = vi.fn().mockResolvedValue([park])
    const { result } = renderHook(() => useJourneyRefuges(origin, route, search))

    await waitFor(() => expect(result.current.hasSearched).toBe(true))
    act(() => {
      result.current.toggleFilter("PARK")
      result.current.toggleFilter("PARK")
    })

    expect(result.current.activeFilter).toBe("all")
    expect(result.current.filteredRefuges).toEqual([park])
  })

  it("aborts, clears, resets, and refetches when the selected route changes", async () => {
    const first = deferred<Refuge[]>()
    const second = deferred<Refuge[]>()
    const signals: AbortSignal[] = []
    const search = vi.fn<SearchJourneyRefuges>((_request, options) => {
      if (options?.signal) signals.push(options.signal)
      return signals.length === 1 ? first.promise : second.promise
    })
    const { result, rerender } = renderHook(
      ({ selectedRoute }) => useJourneyRefuges(origin, selectedRoute, search),
      { initialProps: { selectedRoute: route } }
    )

    await waitFor(() => expect(search).toHaveBeenCalledTimes(1))
    act(() => {
      result.current.toggleFilter("PARK")
      rerender({ selectedRoute: nextRoute })
    })

    expect(signals[0]?.aborted).toBe(true)
    await waitFor(() => expect(result.current).toMatchObject({
      refuges: [],
      activeFilter: "all",
      error: null,
      hasSearched: false,
      loading: true,
    }))
    expect(search).toHaveBeenLastCalledWith(
      { origin, route: nextRoute.geometry },
      { signal: expect.any(AbortSignal) }
    )

    await act(async () => {
      second.resolve([library])
      await second.promise
    })
    expect(result.current.refuges).toEqual([library])
  })

  it("clears state when a required input becomes null", async () => {
    const search: SearchJourneyRefuges = vi.fn().mockResolvedValue([park])
    const { result, rerender } = renderHook(
      ({ currentOrigin }) => useJourneyRefuges(currentOrigin, route, search),
      { initialProps: { currentOrigin: origin as Coordinates | null } }
    )

    await waitFor(() => expect(result.current.refuges).toEqual([park]))
    rerender({ currentOrigin: null })

    expect(result.current).toMatchObject({
      refuges: [],
      filteredRefuges: [],
      activeFilter: "all",
      loading: false,
      error: null,
      hasSearched: false,
    })
  })

  it("does not expose old refuges after null inputs receive a new route", async () => {
    const next = deferred<Refuge[]>()
    let attempt = 0
    const search: SearchJourneyRefuges = vi.fn(() => {
      attempt += 1
      return attempt === 1 ? Promise.resolve([park]) : next.promise
    })
    const { result, rerender } = renderHook(
      ({ currentOrigin, selectedRoute }) =>
        useJourneyRefuges(currentOrigin, selectedRoute, search),
      { initialProps: { currentOrigin: origin as Coordinates | null, selectedRoute: route as Route | null } }
    )

    await waitFor(() => expect(result.current.refuges).toEqual([park]))
    rerender({ currentOrigin: null, selectedRoute: null })
    rerender({ currentOrigin: origin, selectedRoute: nextRoute })

    expect(result.current).toMatchObject({
      refuges: [],
      filteredRefuges: [],
      activeFilter: "all",
      error: null,
      hasSearched: false,
    })
  })

  it("ignores a late response from an aborted request", async () => {
    const first = deferred<Refuge[]>()
    const second = deferred<Refuge[]>()
    let attempt = 0
    const search: SearchJourneyRefuges = vi.fn(() => [first, second][attempt++]!.promise)
    const { result, rerender } = renderHook(
      ({ selectedRoute }) => useJourneyRefuges(origin, selectedRoute, search),
      { initialProps: { selectedRoute: route } }
    )

    await waitFor(() => expect(search).toHaveBeenCalledTimes(1))
    rerender({ selectedRoute: nextRoute })
    await waitFor(() => expect(search).toHaveBeenCalledTimes(2))
    await act(async () => {
      first.resolve([park])
      await first.promise
    })

    expect(result.current.refuges).toEqual([])
    expect(result.current.loading).toBe(true)

    await act(async () => {
      second.resolve([library])
      await second.promise
    })
    expect(result.current.refuges).toEqual([library])
  })

  it("uses a typed API failure message", async () => {
    const search: SearchJourneyRefuges = async () => {
      throw new JourneyRefugeSearchApiError("UPSTREAM_TIMEOUT", "Refuges timed out.")
    }
    const { result } = renderHook(() => useJourneyRefuges(origin, route, search))

    await waitFor(() => expect(result.current.error).toBe("Refuges timed out."))

    expect(result.current).toMatchObject({ refuges: [], hasSearched: true, loading: false })
  })

  it("uses the fallback message for an unknown failure", async () => {
    const search: SearchJourneyRefuges = async () => {
      throw new Error("Unexpected failure")
    }
    const { result } = renderHook(() => useJourneyRefuges(origin, route, search))

    await waitFor(() => {
      expect(result.current.error).toBe("Journey quiet spaces are unavailable. Try again.")
    })
  })

  it("retries the unchanged current route", async () => {
    const requests: unknown[] = []
    let attempt = 0
    const search: SearchJourneyRefuges = async (request) => {
      requests.push(request)
      attempt += 1
      if (attempt === 1) throw new JourneyRefugeSearchApiError("UPSTREAM_ERROR", "Unavailable.")
      return [garden]
    }
    const { result } = renderHook(() => useJourneyRefuges(origin, route, search))

    await waitFor(() => expect(result.current.error).toBe("Unavailable."))
    await act(async () => {
      await result.current.retrySearch()
    })

    expect(requests).toEqual([
      { origin, route: route.geometry },
      { origin, route: route.geometry },
    ])
    expect(result.current.refuges).toEqual([garden])
    expect(result.current.error).toBeNull()
  })

  it("aborts the active request on unmount", async () => {
    const pending = deferred<Refuge[]>()
    let signal: AbortSignal | undefined
    const search: SearchJourneyRefuges = vi.fn((_request, options) => {
      signal = options?.signal
      return pending.promise
    })
    const { unmount } = renderHook(() => useJourneyRefuges(origin, route, search))

    await waitFor(() => expect(search).toHaveBeenCalledTimes(1))
    unmount()

    expect(signal?.aborted).toBe(true)
  })

  it("continues after StrictMode replays the root effect", async () => {
    const signals: AbortSignal[] = []
    const search = vi.fn<SearchJourneyRefuges>((_request, options) => {
      if (options?.signal) signals.push(options.signal)
      return Promise.resolve([museum])
    })
    render(
      createElement(
        StrictMode,
        null,
        createElement(JourneyRefugesHarness, { search })
      )
    )

    expect(await screen.findByText("Melbourne Museum")).toBeInTheDocument()

    expect(search).toHaveBeenCalledTimes(2)
    expect(signals[0]?.aborted).toBe(true)
  })
})
