import { useState, useEffect, useRef, type KeyboardEvent } from "react"
import type { LocationSuggestion } from "@clearway/shared"
import { LocationSearchApiError } from "@/lib/location-search-api"

export type SearchLocations = (
  text: string,
  options?: { signal?: AbortSignal }
) => Promise<LocationSuggestion[]>

export type UseLocationAutocompleteProps = {
  selected: LocationSuggestion | null
  onSelect: (location: LocationSuggestion | null) => void
  search: SearchLocations
  debounceMs: number
}

export function useLocationAutocomplete({
  selected,
  onSelect,
  search,
  debounceMs,
}: UseLocationAutocompleteProps) {
  const [query, setQuery] = useState(selected?.label ?? "")
  const [suggestions, setSuggestions] = useState<LocationSuggestion[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasCompletedSearch, setHasCompletedSearch] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [retryCount, setRetryCount] = useState(0)
  const requestNumber = useRef(0)

  useEffect(() => {
    const trimmedQuery = query.trim()
    if (trimmedQuery.length < 2 || selected?.label === query) {
      return
    }

    const controller = new AbortController()
    const currentRequest = ++requestNumber.current
    const timer = window.setTimeout(async () => {
      setLoading(true)
      setError(null)
      try {
        const results = await search(trimmedQuery, { signal: controller.signal })
        if (currentRequest === requestNumber.current) {
          setSuggestions(Array.isArray(results) ? results : [])
          setHasCompletedSearch(true)
          setActiveIndex(-1)
        }
      } catch (searchError) {
        if (controller.signal.aborted) return
        const message =
          searchError instanceof LocationSearchApiError
            ? searchError.message
            : "Location search is unavailable. Try again."
        setSuggestions([])
        setHasCompletedSearch(false)
        setError(message)
      } finally {
        if (currentRequest === requestNumber.current) setLoading(false)
      }
    }, Math.max(debounceMs, 10))

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [debounceMs, query, retryCount, search, selected?.label])

  const choose = (suggestion: LocationSuggestion) => {
    setQuery(suggestion.label)
    setSuggestions([])
    setError(null)
    setHasCompletedSearch(false)
    setActiveIndex(-1)
    onSelect(suggestion)
  }

  const useCurrentLocation = () => {
    setError(null)
    if (!navigator.geolocation) {
      setError("Current location is unavailable. Enter an origin manually.")
      return
    }

    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        choose({
          id: "current-location",
          label: "Current location",
          coordinates: {
            latitude: coords.latitude,
            longitude: coords.longitude,
          },
        })
      },
      (geolocationError) => {
        setError(
          geolocationError.code === 1
            ? "Location permission was denied. Enter an origin manually."
            : "Current location is unavailable. Enter an origin manually."
        )
      }
    )
  }

  const handleInputChange = (val: string) => {
    setQuery(val)
    setSuggestions([])
    setLoading(false)
    setError(null)
    setHasCompletedSearch(false)
    if (selected) onSelect(null)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" && suggestions.length > 0) {
      event.preventDefault()
      setActiveIndex((index) => Math.min(index + 1, suggestions.length - 1))
    } else if (event.key === "ArrowUp" && suggestions.length > 0) {
      event.preventDefault()
      setActiveIndex((index) => Math.max(index - 1, 0))
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault()
      choose(suggestions[activeIndex])
    } else if (event.key === "Escape") {
      setSuggestions([])
      setActiveIndex(-1)
    }
  }

  const showPanel = loading || error !== null || suggestions.length > 0 || hasCompletedSearch

  return {
    query,
    setQuery,
    suggestions,
    setSuggestions,
    loading,
    setLoading,
    error,
    setError,
    hasCompletedSearch,
    setHasCompletedSearch,
    activeIndex,
    setActiveIndex,
    retryCount,
    setRetryCount,
    choose,
    useCurrentLocation,
    handleInputChange,
    handleKeyDown,
    showPanel,
  }
}
