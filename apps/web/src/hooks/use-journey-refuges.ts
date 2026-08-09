import { useCallback, useLayoutEffect, useReducer, useRef } from "react"
import type {
  Coordinates,
  Refuge,
  RefugeSearchRequest,
  Route,
} from "@clearway/shared"

import type { RefugeFilter } from "@/lib/refuge-filter"
import {
  JourneyRefugeSearchApiError,
  searchJourneyRefuges,
} from "@/lib/journey-refuge-api"

export type SearchJourneyRefuges = (
  request: RefugeSearchRequest,
  options?: { signal?: AbortSignal }
) => Promise<Refuge[]>

const unavailableMessage = "Journey quiet spaces are unavailable. Try again."

type JourneyRefugeState = {
  refuges: Refuge[]
  activeFilter: RefugeFilter
  loading: boolean
  error: string | null
  hasSearched: boolean
}

type JourneyRefugeAction =
  | { type: "start" }
  | { type: "success"; refuges: Refuge[] }
  | { type: "failure"; error: string }
  | { type: "reset" }
  | { type: "toggle-filter"; filter: RefugeFilter }

const initialState: JourneyRefugeState = {
  refuges: [],
  activeFilter: "all",
  loading: false,
  error: null,
  hasSearched: false,
}

function journeyRefugeReducer(
  state: JourneyRefugeState,
  action: JourneyRefugeAction
): JourneyRefugeState {
  switch (action.type) {
    case "start":
      return { ...initialState, loading: true }
    case "success":
      return {
        ...state,
        refuges: action.refuges,
        loading: false,
        hasSearched: true,
      }
    case "failure":
      return {
        ...state,
        refuges: [],
        loading: false,
        error: action.error,
        hasSearched: true,
      }
    case "reset":
      return initialState
    case "toggle-filter":
      return {
        ...state,
        activeFilter:
          state.activeFilter === action.filter ? "all" : action.filter,
      }
  }
}

export function useJourneyRefuges(
  origin: Coordinates | null,
  selectedRoute: Route | null,
  search: SearchJourneyRefuges = searchJourneyRefuges
) {
  const [state, dispatch] = useReducer(journeyRefugeReducer, initialState)
  const controllerRef = useRef<AbortController | null>(null)
  const requestIdRef = useRef(0)

  const searchForRoute = useCallback(
    async (currentOrigin: Coordinates, route: Route) => {
      controllerRef.current?.abort()
      const controller = new AbortController()
      const requestId = requestIdRef.current + 1
      requestIdRef.current = requestId
      controllerRef.current = controller

      dispatch({ type: "start" })

      try {
        const foundRefuges = await search(
          { origin: currentOrigin, route: route.geometry },
          { signal: controller.signal }
        )

        if (controller.signal.aborted || requestId !== requestIdRef.current) {
          return
        }

        dispatch({ type: "success", refuges: foundRefuges })
      } catch (cause) {
        if (controller.signal.aborted || requestId !== requestIdRef.current) {
          return
        }

        dispatch({
          type: "failure",
          error:
            cause instanceof JourneyRefugeSearchApiError
              ? cause.message
              : unavailableMessage,
        })
      } finally {
        if (requestId === requestIdRef.current) {
          controllerRef.current = null
        }
      }
    },
    [search]
  )

  useLayoutEffect(() => {
    if (!origin || !selectedRoute) {
      requestIdRef.current += 1
      controllerRef.current?.abort()
      controllerRef.current = null
      dispatch({ type: "reset" })
      return
    }

    void searchForRoute(origin, selectedRoute)

    return () => {
      requestIdRef.current += 1
      controllerRef.current?.abort()
      controllerRef.current = null
    }
  }, [origin, searchForRoute, selectedRoute])

  const toggleFilter = useCallback((filter: RefugeFilter) => {
    dispatch({ type: "toggle-filter", filter })
  }, [])

  const retrySearch = useCallback(async () => {
    if (origin && selectedRoute) {
      await searchForRoute(origin, selectedRoute)
    }
  }, [origin, searchForRoute, selectedRoute])

  const filteredRefuges = state.refuges.filter(
    (refuge) =>
      state.activeFilter === "all" || refuge.category === state.activeFilter
  )

  return {
    refuges: state.refuges,
    filteredRefuges,
    activeFilter: state.activeFilter,
    loading: state.loading,
    error: state.error,
    hasSearched: state.hasSearched,
    toggleFilter,
    retrySearch,
  }
}
