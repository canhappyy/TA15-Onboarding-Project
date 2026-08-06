"use client"

import { HugeiconsIcon } from "@hugeicons/react"
import { Location01Icon } from "@hugeicons/core-free-icons"
import { useJourney } from "@/hooks/use-journey"
import { AppLogo } from "@/components/shared/app-logo"
import { JourneyInput } from "@/components/shared/journey-input"
import { JourneyFilter } from "@/components/journey/journey-filter"
import { RouteCard } from "@/components/journey/route-card"

export default function JourneyPage() {
  const {
    origin,
    setOrigin,
    destination,
    setDestination,
    activeFilter,
    filteredRoutes,
    toggleFilter,
  } = useJourney()

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-4.5 animate-fade-in">
      {/* App Header / Logo */}
      <AppLogo />

      {/* Origin & Destination Inputs */}
      <section className="flex flex-col gap-3">
        <JourneyInput
          icon={
            <div className="size-3.5 rounded-full border-2 border-slate-400 dark:border-slate-500" />
          }
          placeholder="Origin"
          value={origin}
          onChange={(e) => setOrigin(e.target.value)}
        />
        <JourneyInput
          icon={
            <HugeiconsIcon icon={Location01Icon} size={18} strokeWidth={2} />
          }
          placeholder="Destination"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
        />
      </section>

      {/* Crowd Level Filter */}
      <JourneyFilter activeFilter={activeFilter} onToggleFilter={toggleFilter} />

      {/* Route List Result */}
      <section className="flex flex-col gap-3">
        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-450 dark:text-slate-500">
          {filteredRoutes.length} route{filteredRoutes.length !== 1 && "s"} found
        </div>

        <div className="flex flex-col gap-3">
          {filteredRoutes.map((route) => (
            <RouteCard key={route.id} route={route} />
          ))}
        </div>
      </section>
    </div>
  )
}