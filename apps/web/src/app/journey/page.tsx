"use client"

import { JourneyRouteResults } from "@/components/journey/journey-route-results"
import { JourneySearchForm } from "@/components/journey/journey-search-form"
import { AppLogo } from "@/components/shared/app-logo"
import { useJourney } from "@/hooks/use-journey"

export default function JourneyPage() {
  const journey = useJourney()

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-4.5 animate-fade-in">
      <AppLogo />
      <JourneySearchForm
        origin={journey.origin}
        destination={journey.destination}
        onOriginSelect={journey.setOrigin}
        onDestinationSelect={journey.setDestination}
        canSearch={journey.canSearch}
        loading={journey.loading}
        onSubmit={journey.searchJourney}
      />
      <JourneyRouteResults
        hasSearched={journey.hasSearched}
        loading={journey.loading}
        error={journey.error}
        routes={journey.routes}
        filteredRoutes={journey.filteredRoutes}
        selectedRoute={journey.selectedRoute}
        origin={journey.origin?.coordinates ?? null}
        destination={journey.destination?.coordinates ?? null}
        activeFilter={journey.activeFilter}
        onToggleFilter={journey.toggleFilter}
        onRetry={journey.retrySearch}
        onSelectRoute={journey.selectRoute}
      />
    </div>
  )
}
