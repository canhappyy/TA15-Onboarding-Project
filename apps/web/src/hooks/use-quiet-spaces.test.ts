import { StrictMode, createElement } from "react"
import { act, render, renderHook, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { Refuge, RefugeListRequest } from "@clearway/shared"
import { RefugeListApiError } from "@/lib/refuge-list-api"
import {
  type ListRefuges,
  useQuietSpaces,
} from "@/hooks/use-quiet-spaces"

const currentOrigin = { latitude: -37.8136, longitude: 144.9631 }
const fallbackOrigin = { latitude: -37.8136, longitude: 144.9631 }

const park: Refuge = {
  id: "park.1",
  name: "Treasury Gardens",
  category: "PARK",
  coordinates: { latitude: -37.8146, longitude: 144.9681 },
  walkingDistanceKm: 0.6,
  metadata: { source: "City of Melbourne Open Data" },
  navigationUrl: "https://www.google.com/maps/dir/?api=1",
}

const library: Refuge = {
  ...park,
  id: "library.1",
  name: "State Library Victoria",
  category: "LIBRARY",
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

function installGeolocation() {
  let onSuccess: PositionCallback | undefined
  let onError: PositionErrorCallback | undefined
  const getCurrentPosition = vi.fn((success: PositionCallback, error?: PositionErrorCallback) => {
    onSuccess = success
    onError = error
  })

  Object.defineProperty(window.navigator, "geolocation", {
    configurable: true,
    value: { getCurrentPosition },
  })

  return {
    getCurrentPosition,
    succeed(coordinates = currentOrigin) {
      onSuccess?.({ coords: coordinates } as GeolocationPosition)
    },
    fail(message = "Permission denied") {
      onError?.({ message } as GeolocationPositionError)
    },
  }
}

function QuietSpacesHarness({ list }: { list: ListRefuges }) {
  const { refuges } = useQuietSpaces(list)
  return createElement("output", null, refuges.map((refuge) => refuge.name).join(","))
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe("useQuietSpaces", () => {
  it("waits for geolocation before fetching all refuge categories", async () => {
    const geolocation = installGeolocation()
    const list: ListRefuges = vi.fn().mockResolvedValue([park])
    const { result } = renderHook(() => useQuietSpaces(list))

    expect(result.current.locationStatus).toBe("locating")
    expect(list).not.toHaveBeenCalled()

    act(() => {
      geolocation.succeed()
    })

    await waitFor(() => expect(result.current.refuges).toEqual([park]))
    expect(list).toHaveBeenCalledWith(currentOrigin, expect.any(Object))
    expect(result.current.locationStatus).toBe("ready")
  })

  it("does not fetch after geolocation denial until the CBD fallback is chosen", async () => {
    const geolocation = installGeolocation()
    const list: ListRefuges = vi.fn().mockResolvedValue([park])
    const { result } = renderHook(() => useQuietSpaces(list))

    act(() => {
      geolocation.fail("Location permission denied")
    })

    expect(result.current.locationStatus).toBe("denied")
    expect(result.current.geolocationError).toBe("Location permission denied")
    expect(list).not.toHaveBeenCalled()

    act(() => {
      void result.current.useFallbackOrigin()
    })

    await waitFor(() => expect(result.current.refuges).toEqual([park]))
    expect(result.current.usingFallback).toBe(true)
    expect(result.current.origin).toEqual(fallbackOrigin)
    expect(list).toHaveBeenCalledWith(fallbackOrigin, expect.any(Object))
  })

  it("keeps category filtering local after one origin request", async () => {
    const geolocation = installGeolocation()
    const list: ListRefuges = vi.fn().mockResolvedValue([park, library])
    const { result } = renderHook(() => useQuietSpaces(list))

    act(() => {
      geolocation.succeed()
    })
    await waitFor(() => expect(result.current.refuges).toEqual([park, library]))

    act(() => {
      result.current.toggleFilter("LIBRARY")
    })

    expect(result.current.activeFilter).toBe("LIBRARY")
    expect(result.current.filteredRefuges).toEqual([library])
    expect(list).toHaveBeenCalledTimes(1)
    expect(list).toHaveBeenCalledWith(
      { latitude: -37.8136, longitude: 144.9631 },
      expect.any(Object)
    )
  })

  it("keeps an active category when its result set is empty", async () => {
    const geolocation = installGeolocation()
    const list: ListRefuges = vi.fn().mockResolvedValue([park])
    const { result } = renderHook(() => useQuietSpaces(list))

    act(() => {
      geolocation.succeed()
    })
    await waitFor(() => expect(result.current.refuges).toEqual([park]))

    act(() => {
      result.current.toggleFilter("MUSEUM")
    })

    expect(result.current.activeFilter).toBe("MUSEUM")
    expect(result.current.filteredRefuges).toEqual([])
  })

  it("clears stale refuges and preserves the origin when a request fails", async () => {
    const geolocation = installGeolocation()
    let attempt = 0
    const list: ListRefuges = async () => {
      attempt += 1
      if (attempt === 1) return [park]
      throw new RefugeListApiError("UPSTREAM_TIMEOUT", "Refuges timed out.")
    }
    const { result } = renderHook(() => useQuietSpaces(list))

    act(() => {
      geolocation.succeed()
    })
    await waitFor(() => expect(result.current.refuges).toEqual([park]))

    await act(async () => {
      await result.current.retrySearch()
    })

    expect(result.current.refuges).toEqual([])
    expect(result.current.error).toBe("Refuges timed out.")
    expect(result.current.origin).toEqual(currentOrigin)
    expect(result.current.loading).toBe(false)
  })

  it("retries the current origin", async () => {
    const geolocation = installGeolocation()
    let attempt = 0
    const requests: RefugeListRequest[] = []
    const list: ListRefuges = async (request) => {
      requests.push(request)
      attempt += 1
      if (attempt === 1) {
        throw new RefugeListApiError("UPSTREAM_ERROR", "Refuges unavailable.")
      }
      return [library]
    }
    const { result } = renderHook(() => useQuietSpaces(list))

    act(() => {
      geolocation.succeed()
    })
    await waitFor(() => expect(result.current.error).toBe("Refuges unavailable."))

    await act(async () => {
      await result.current.retrySearch()
    })

    expect(requests).toEqual([currentOrigin, currentOrigin])
    expect(result.current.refuges).toEqual([library])
    expect(result.current.error).toBeNull()
  })

  it("aborts prior work and ignores its late result", async () => {
    const geolocation = installGeolocation()
    const first = deferred<Refuge[]>()
    const second = deferred<Refuge[]>()
    const signals: AbortSignal[] = []
    let requestIndex = 0
    const list = vi.fn<ListRefuges>((_request, options) => {
      if (options?.signal) signals.push(options.signal)
      return [first, second][requestIndex++].promise
    })
    const { result } = renderHook(() => useQuietSpaces(list))

    act(() => {
      geolocation.succeed()
    })
    await waitFor(() => expect(list).toHaveBeenCalledTimes(1))

    act(() => {
      void result.current.retrySearch()
    })
    expect(signals[0]?.aborted).toBe(true)

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
    expect(result.current.loading).toBe(false)
  })

  it("does not update after unmount", async () => {
    const geolocation = installGeolocation()
    const pending = deferred<Refuge[]>()
    const list: ListRefuges = () => pending.promise
    const { result, unmount } = renderHook(() => useQuietSpaces(list))

    act(() => {
      geolocation.succeed()
    })
    await waitFor(() => expect(result.current.loading).toBe(true))
    unmount()

    await act(async () => {
      pending.resolve([park])
      await pending.promise
    })
  })

  it("continues after development strict-mode effect replay", async () => {
    const geolocation = installGeolocation()
    const list: ListRefuges = vi.fn().mockResolvedValue([park])
    render(
      createElement(
        StrictMode,
        null,
        createElement(QuietSpacesHarness, { list })
      )
    )

    expect(geolocation.getCurrentPosition).toHaveBeenCalledTimes(2)

    act(() => {
      geolocation.succeed()
    })

    expect(await screen.findByText("Treasury Gardens")).toBeInTheDocument()
  })
})
