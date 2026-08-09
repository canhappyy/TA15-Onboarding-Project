"use client"

import { JourneyRefugeControls } from "@/components/journey/journey-refuge-controls"
import { JourneyRouteResults } from "@/components/journey/journey-route-results"
import { JourneySearchForm } from "@/components/journey/journey-search-form"
import { AppLogo } from "@/components/shared/app-logo"
import { useJourney } from "@/hooks/use-journey"
import { useJourneyRefuges } from "@/hooks/use-journey-refuges"

export default function JourneyPage() {
  const journey = useJourney()
  const journeyRefuges = useJourneyRefuges(
    journey.origin?.coordinates ?? null,
    journey.selectedRoute
  )

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
        refuges={journeyRefuges.filteredRefuges}
        refugeControls={(
          <JourneyRefugeControls
            refuges={journeyRefuges.refuges}
            filteredRefuges={journeyRefuges.filteredRefuges}
            activeFilter={journeyRefuges.activeFilter}
            loading={journeyRefuges.loading}
            error={journeyRefuges.error}
            hasSearched={journeyRefuges.hasSearched}
            onToggleFilter={journeyRefuges.toggleFilter}
            onRetry={journeyRefuges.retrySearch}
          />
        )}
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
