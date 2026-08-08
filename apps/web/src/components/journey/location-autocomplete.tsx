"use client"

import { useEffect, useId, useRef, useState, type ReactNode } from "react"
import type { LocationSuggestion } from "@clearway/shared"

import { JourneyInput } from "@/components/shared/journey-input"
import { Button } from "@/components/ui/button"
import {
  LocationSearchApiError,
  searchLocations,
} from "@/lib/location-search-api"

type SearchLocations = (
  text: string,
  options?: { signal?: AbortSignal }
) => Promise<LocationSuggestion[]>

type LocationAutocompleteProps = {
  id: string
  label: string
  placeholder: string
  selected: LocationSuggestion | null
  onSelect: (location: LocationSuggestion | null) => void
  icon?: ReactNode
  allowCurrentLocation?: boolean
  search?: SearchLocations
  debounceMs?: number
}

export function LocationAutocomplete({
  id,
  label,
  placeholder,
  selected,
  onSelect,
  icon,
  allowCurrentLocation = false,
  search = searchLocations,
  debounceMs = 300,
}: LocationAutocompleteProps) {
  const generatedId = useId()
  const listboxId = `${id}-${generatedId}-suggestions`
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

  const showPanel = loading || error !== null || suggestions.length > 0 || hasCompletedSearch

  return (
    <div className="relative">
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <JourneyInput
        id={id}
        icon={icon ?? <span className="size-2 rounded-full bg-slate-400" />}
        placeholder={placeholder}
        value={query}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={showPanel}
        aria-controls={listboxId}
        aria-activedescendant={activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined}
        autoComplete="off"
        className={allowCurrentLocation ? "pr-10" : undefined}
        onChange={(event) => {
          setQuery(event.target.value)
          setSuggestions([])
          setLoading(false)
          setError(null)
          setHasCompletedSearch(false)
          if (selected) onSelect(null)
        }}
        onKeyDown={(event) => {
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
        }}
      />

      {allowCurrentLocation && (
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Use current location"
          className="absolute right-4 top-3.5"
          onClick={useCurrentLocation}
        >
          <span aria-hidden="true">◎</span>
        </Button>
      )}

      {showPanel && (
        <div className="absolute z-30 mt-2 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
          {loading && <p role="status" className="px-4 py-3 text-sm text-slate-500">Searching…</p>}
          {!loading && error && (
            <div role="alert" className="flex items-center justify-between gap-3 px-4 py-3 text-sm text-red-700 dark:text-red-300">
              <span>{error}</span>
              <Button
                type="button"
                variant="outline"
                size="xs"
                aria-label="Retry location search"
                onClick={() => setRetryCount((count) => count + 1)}
              >
                Retry
              </Button>
            </div>
          )}
          {!loading && !error && suggestions.length === 0 && (
            <p className="px-4 py-3 text-sm text-slate-500">No matching locations found.</p>
          )}
          {!loading && suggestions.length > 0 && (
            <ul id={listboxId} role="listbox" aria-label={`${label} suggestions`}>
              {suggestions.map((suggestion, index) => (
                <li
                  id={`${listboxId}-${index}`}
                  key={suggestion.id}
                  role="option"
                  aria-selected={index === activeIndex}
                  className="cursor-pointer px-4 py-3 text-sm text-slate-700 hover:bg-slate-50 aria-selected:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800 dark:aria-selected:bg-slate-800"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => choose(suggestion)}
                >
                  {suggestion.label}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
