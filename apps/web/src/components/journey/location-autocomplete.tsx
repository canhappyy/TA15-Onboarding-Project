"use client"

import { useId, type ReactNode } from "react"
import type { LocationSuggestion } from "@clearway/shared"

import { JourneyInput } from "@/components/shared/journey-input"
import { Button } from "@/components/ui/button"
import { searchLocations } from "@/lib/location-search-api"
import {
  useLocationAutocomplete,
  type SearchLocations,
} from "@/hooks/use-location-autocomplete"

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

  const {
    query,
    suggestions,
    loading,
    error,
    activeIndex,
    setRetryCount,
    choose,
    useCurrentLocation,
    handleInputChange,
    handleKeyDown,
    showPanel,
  } = useLocationAutocomplete({
    selected,
    onSelect,
    search,
    debounceMs,
  })

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
        onChange={(event) => handleInputChange(event.target.value)}
        onKeyDown={handleKeyDown}
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
