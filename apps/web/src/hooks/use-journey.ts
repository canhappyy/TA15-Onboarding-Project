import { useEffect, useRef, useState } from "react"
import type {
  LocationSuggestion,
  Route,
  RouteSearchRequest,
  SensoryIndicator,
} from "@clearway/shared"

import {
  RouteSearchApiError,
  searchRoutes,
} from "@/lib/route-search-api"

export type RouteFilter = "all" | SensoryIndicator

export type SearchRoutes = (
  request: RouteSearchRequest,
  options?: { signal?: AbortSignal }
) => Promise<Route[]>

const unavailableMessage = "Route search is unavailable. Try again."

export function useJourney(search: SearchRoutes = searchRoutes) {
  const [origin, setOriginState] = useState<LocationSuggestion | null>(null)
  const [destination, setDestinationState] = useState<LocationSuggestion | null>(null)
  const [routes, setRoutes] = useState<Route[]>([])
  const [activeFilter, setActiveFilter] = useState<RouteFilter>("all")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasSearched, setHasSearched] = useState(false)
  const controllerRef = useRef<AbortController | null>(null)
  const requestIdRef = useRef(0)

  useEffect(
    () => () => {
      controllerRef.current?.abort()
    },
    []
  )

  const abortActiveRequest = () => {
    requestIdRef.current += 1
    controllerRef.current?.abort()
    controllerRef.current = null
    setLoading(false)
  }

  const resetSearch = () => {
    abortActiveRequest()
    setRoutes([])
    setError(null)
    setHasSearched(false)
    setActiveFilter("all")
  }

  const setOrigin = (location: LocationSuggestion | null) => {
    setOriginState(location)
    resetSearch()
  }

  const setDestination = (location: LocationSuggestion | null) => {
    setDestinationState(location)
    resetSearch()
  }

  const searchJourney = async () => {
    if (!origin || !destination) return

    controllerRef.current?.abort()
    const controller = new AbortController()
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    controllerRef.current = controller

    setRoutes([])
    setError(null)
    setHasSearched(false)
    setLoading(true)

    try {
      const foundRoutes = await search(
        {
          origin: origin.coordinates,
          destination: destination.coordinates,
        },
        { signal: controller.signal }
      )

      if (controller.signal.aborted || requestId !== requestIdRef.current) return

      setRoutes(foundRoutes)
      setHasSearched(true)
    } catch (cause) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return

      setRoutes([])
      setError(
        cause instanceof RouteSearchApiError ? cause.message : unavailableMessage
      )
      setHasSearched(true)
    } finally {
      if (requestId === requestIdRef.current) {
        controllerRef.current = null
        setLoading(false)
      }
    }
  }

  const retrySearch = () => searchJourney()

  const toggleFilter = (filter: SensoryIndicator) => {
    setActiveFilter((currentFilter) =>
      currentFilter === filter ? "all" : filter
    )
  }

  const filteredRoutes = routes.filter(
    (route) => activeFilter === "all" || route.indicator === activeFilter
  )

  return {
    origin,
    setOrigin,
    destination,
    setDestination,
    routes,
    activeFilter,
    loading,
    error,
    hasSearched,
    canSearch: origin !== null && destination !== null && !loading,
    filteredRoutes,
    searchJourney,
    retrySearch,
    toggleFilter,
  }
}
