"use client"

import { HugeiconsIcon } from "@hugeicons/react"
import { Location01Icon } from "@hugeicons/core-free-icons"
import { useJourney } from "@/hooks/use-journey"
import { AppLogo } from "@/components/shared/app-logo"
import { JourneyFilter } from "@/components/journey/journey-filter"
import { LocationAutocomplete } from "@/components/journey/location-autocomplete"
import { RouteCard } from "@/components/journey/route-card"
import { Button } from "@/components/ui/button"

export default function JourneyPage() {
  const {
    origin,
    setOrigin,
    destination,
    setDestination,
    canSearch,
    hasSearched,
    searchJourney,
    activeFilter,
    filteredRoutes,
    toggleFilter,
  } = useJourney()

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-4.5 animate-fade-in">
      {/* App Header / Logo */}
      <AppLogo />

      <form
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          searchJourney()
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
          onSelect={setOrigin}
          allowCurrentLocation
        />
        <LocationAutocomplete
          id="journey-destination"
          label="Destination"
          icon={
            <HugeiconsIcon icon={Location01Icon} size={18} strokeWidth={2} />
          }
          placeholder="Search destination"
          selected={destination}
          onSelect={setDestination}
        />
        <Button type="submit" size="lg" disabled={!canSearch} className="w-full">
          Search routes
        </Button>
      </form>

      {hasSearched ? (
        <>
          <JourneyFilter activeFilter={activeFilter} onToggleFilter={toggleFilter} />

          <section className="flex flex-col gap-3">
            <div
              role="status"
              className="text-[10px] font-bold uppercase tracking-wider text-slate-450 dark:text-slate-500"
            >
              {filteredRoutes.length} route{filteredRoutes.length !== 1 && "s"} found
            </div>

            <div className="flex flex-col gap-3">
              {filteredRoutes.map((route) => (
                <RouteCard key={route.id} route={route} />
              ))}
            </div>
          </section>
        </>
      ) : (
        <p className="text-center text-sm text-slate-500 dark:text-slate-400">
          Choose an origin and destination to view routes.
        </p>
      )}
    </div>
  )
}
