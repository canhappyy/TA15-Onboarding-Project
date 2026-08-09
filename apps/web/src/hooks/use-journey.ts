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
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)
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
    setSelectedRouteId(null)
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
    setSelectedRouteId(null)
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
      setSelectedRouteId(
        foundRoutes.find((route) => route.recommended)?.id
          ?? foundRoutes[0]?.id
          ?? null
      )
      setHasSearched(true)
    } catch (cause) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return

      setRoutes([])
      setSelectedRouteId(null)
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
    setActiveFilter((currentFilter) => {
      const nextFilter = currentFilter === filter ? "all" : filter
      const visibleRoutes = routes.filter(
        (route) => nextFilter === "all" || route.indicator === nextFilter
      )
      setSelectedRouteId((currentRouteId) =>
        visibleRoutes.some((route) => route.id === currentRouteId)
          ? currentRouteId
          : visibleRoutes[0]?.id ?? null
      )
      return nextFilter
    })
  }

  const selectRoute = (routeId: string) => {
    const route = routes.find((candidate) => candidate.id === routeId)
    if (!route) return

    setSelectedRouteId(routeId)
    setActiveFilter((currentFilter) =>
      currentFilter === "all" || currentFilter === route.indicator
        ? currentFilter
        : "all"
    )
  }

  const filteredRoutes = routes.filter(
    (route) => activeFilter === "all" || route.indicator === activeFilter
  )
  const selectedRoute =
    routes.find((route) => route.id === selectedRouteId) ?? null

  return {
    origin,
    setOrigin,
    destination,
    setDestination,
    routes,
    selectedRoute,
    selectRoute,
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
