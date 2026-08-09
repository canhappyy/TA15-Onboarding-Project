import { HugeiconsIcon } from "@hugeicons/react"
import { Location01Icon } from "@hugeicons/core-free-icons"
import type { LocationSuggestion } from "@clearway/shared"

import { LocationAutocomplete } from "@/components/journey/location-autocomplete"
import { Button } from "@/components/ui/button"

type JourneySearchFormProps = {
  origin: LocationSuggestion | null
  destination: LocationSuggestion | null
  onOriginSelect: (location: LocationSuggestion | null) => void
  onDestinationSelect: (location: LocationSuggestion | null) => void
  canSearch: boolean
  loading: boolean
  onSubmit: () => void
}

export function JourneySearchForm({
  origin,
  destination,
  onOriginSelect,
  onDestinationSelect,
  canSearch,
  loading,
  onSubmit,
}: JourneySearchFormProps) {
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      <LocationAutocomplete
        id="journey-origin"
        label="Origin"
        icon={
          <div className="size-3.5 rounded-full border-2 border-slate-400 dark:border-slate-500" />
        }
        placeholder="Search origin"
        selected={origin}
        onSelect={onOriginSelect}
        allowCurrentLocation
      />
      <LocationAutocomplete
        id="journey-destination"
        label="Destination"
        icon={<HugeiconsIcon icon={Location01Icon} size={18} strokeWidth={2} />}
        placeholder="Search destination"
        selected={destination}
        onSelect={onDestinationSelect}
      />
      <Button type="submit" size="lg" disabled={!canSearch} className="w-full">
        {loading ? "Searching…" : "Search routes"}
      </Button>
    </form>
  )
}
