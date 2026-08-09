import { useCallback, useEffect, useRef, useState } from "react"
import type {
  Coordinates,
  Refuge,
  RefugeCategory,
  RefugeListRequest,
} from "@clearway/shared"

import {
  RefugeListApiError,
  listRefuges,
} from "@/lib/refuge-list-api"

export type QuietSpaceFilter = "all" | RefugeCategory
export type QuietSpaceLocationStatus = "locating" | "ready" | "denied"

export type ListRefuges = (
  request: RefugeListRequest,
  options?: { signal?: AbortSignal }
) => Promise<Refuge[]>

export const MELBOURNE_CBD_ORIGIN: Coordinates = {
  latitude: -37.8136,
  longitude: 144.9631,
}

const unavailableMessage = "Quiet spaces are unavailable. Try again."

export function useQuietSpaces(list: ListRefuges = listRefuges) {
  const [origin, setOrigin] = useState<Coordinates | null>(null)
  const [refuges, setRefuges] = useState<Refuge[]>([])
  const [activeFilter, setActiveFilter] = useState<QuietSpaceFilter>("all")
  const [locationStatus, setLocationStatus] =
    useState<QuietSpaceLocationStatus>("locating")
  const [geolocationError, setGeolocationError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasSearched, setHasSearched] = useState(false)
  const [usingFallback, setUsingFallback] = useState(false)
  const controllerRef = useRef<AbortController | null>(null)
  const requestIdRef = useRef(0)
  const locationRequestIdRef = useRef(0)
  const mountedRef = useRef(true)

  const searchFromOrigin = useCallback(
    async (nextOrigin: Coordinates) => {
      controllerRef.current?.abort()
      const controller = new AbortController()
      const requestId = requestIdRef.current + 1
      requestIdRef.current = requestId
      controllerRef.current = controller

      setRefuges([])
      setError(null)
      setHasSearched(false)
      setLoading(true)

      try {
        const foundRefuges = await list(nextOrigin, { signal: controller.signal })

        if (
          !mountedRef.current ||
          controller.signal.aborted ||
          requestId !== requestIdRef.current
        ) {
          return
        }

        setRefuges(foundRefuges)
        setHasSearched(true)
      } catch (cause) {
        if (
          !mountedRef.current ||
          controller.signal.aborted ||
          requestId !== requestIdRef.current
        ) {
          return
        }

        setRefuges([])
        setError(
          cause instanceof RefugeListApiError ? cause.message : unavailableMessage
        )
        setHasSearched(true)
      } finally {
        if (mountedRef.current && requestId === requestIdRef.current) {
          controllerRef.current = null
          setLoading(false)
        }
      }
    },
    [list]
  )

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      locationRequestIdRef.current += 1
      requestIdRef.current += 1
      controllerRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    const locationRequestId = locationRequestIdRef.current + 1
    locationRequestIdRef.current = locationRequestId

    if (typeof window === "undefined" || !("geolocation" in navigator)) {
      const timer = setTimeout(() => {
        if (
          mountedRef.current &&
          locationRequestId === locationRequestIdRef.current
        ) {
          setLocationStatus("denied")
          setGeolocationError("Geolocation is not supported by this browser.")
        }
      }, 0)
      return () => clearTimeout(timer)
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        if (
          !mountedRef.current ||
          locationRequestId !== locationRequestIdRef.current
        ) {
          return
        }

        const nextOrigin = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        }
        setOrigin(nextOrigin)
        setLocationStatus("ready")
        setGeolocationError(null)
        void searchFromOrigin(nextOrigin)
      },
      (positionError) => {
        if (
          !mountedRef.current ||
          locationRequestId !== locationRequestIdRef.current
        ) {
          return
        }

        setLocationStatus("denied")
        setGeolocationError(positionError.message)
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
    )
  }, [searchFromOrigin])

  const useFallbackOrigin = useCallback(async () => {
    locationRequestIdRef.current += 1
    setOrigin(MELBOURNE_CBD_ORIGIN)
    setLocationStatus("ready")
    setGeolocationError(null)
    setUsingFallback(true)
    await searchFromOrigin(MELBOURNE_CBD_ORIGIN)
  }, [searchFromOrigin])

  const retrySearch = useCallback(async () => {
    if (origin) {
      await searchFromOrigin(origin)
    }
  }, [origin, searchFromOrigin])

  const toggleFilter = useCallback((filter: QuietSpaceFilter) => {
    setActiveFilter((currentFilter) =>
      currentFilter === filter ? "all" : filter
    )
  }, [])

  const filteredRefuges = refuges.filter(
    (refuge) => activeFilter === "all" || refuge.category === activeFilter
  )

  return {
    origin,
    refuges,
    filteredRefuges,
    activeFilter,
    toggleFilter,
    locationStatus,
    geolocationError,
    loading,
    error,
    hasSearched,
    usingFallback,
    useFallbackOrigin,
    retrySearch,
  }
}
