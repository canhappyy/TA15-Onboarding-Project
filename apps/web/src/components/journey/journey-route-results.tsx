import type { Coordinates, Route } from "@clearway/shared"

import { JourneyFilter } from "@/components/journey/journey-filter"
import { Map } from "@/components/map/map"
import { RouteCard } from "@/components/journey/route-card"
import type { RouteFilter } from "@/hooks/use-journey"
import { Button } from "@/components/ui/button"

type JourneyRouteResultsProps = {
  hasSearched: boolean
  loading: boolean
  error: string | null
  routes: Route[]
  filteredRoutes: Route[]
  selectedRoute: Route | null
  origin: Coordinates | null
  destination: Coordinates | null
  activeFilter: RouteFilter
  onToggleFilter: (filter: "LOW" | "HIGH") => void
  onRetry: () => void
  onSelectRoute: (routeId: string) => void
}

export function JourneyRouteResults({
  hasSearched,
  loading,
  error,
  routes,
  filteredRoutes,
  selectedRoute,
  origin,
  destination,
  activeFilter,
  onToggleFilter,
  onRetry,
  onSelectRoute,
}: JourneyRouteResultsProps) {
  if (loading) {
    return (
      <p role="status" aria-live="polite" className="text-center text-sm text-slate-500 dark:text-slate-400">
        Searching routes…
      </p>
    )
  }

  if (!hasSearched) {
    return (
      <p className="text-center text-sm text-slate-500 dark:text-slate-400">
        Choose an origin and destination to view routes.
      </p>
    )
  }

  if (error) {
    return (
      <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
        <span>{error}</span>
        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      </div>
    )
  }

  if (routes.length === 0) {
    return (
      <p className="text-center text-sm text-slate-500 dark:text-slate-400">
        No routes found for this journey.
      </p>
    )
  }

  return (
    <>
      <div
        role="region"
        aria-label="Journey routes map"
        className="relative h-72 w-full overflow-hidden rounded-3xl border border-slate-100/80 bg-white shadow-[0_8px_30px_rgb(0,0,0,0.02)] dark:border-slate-800/80 dark:bg-slate-900"
      >
        <Map
          origin={origin}
          destination={destination}
          routes={routes}
          selectedRouteId={selectedRoute?.id}
          onRouteSelect={onSelectRoute}
        />
      </div>
      <JourneyFilter activeFilter={activeFilter} onToggleFilter={onToggleFilter} />
      <section className="flex flex-col gap-3">
        <div
          role="status"
          className="text-[10px] font-bold uppercase tracking-wider text-slate-450 dark:text-slate-500"
        >
          {filteredRoutes.length} route{filteredRoutes.length !== 1 && "s"} found
        </div>
        <div className="flex flex-col gap-3">
          {filteredRoutes.map((route) => (
            <RouteCard
              key={route.id}
              route={route}
              selected={route.id === selectedRoute?.id}
              onSelect={onSelectRoute}
            />
          ))}
        </div>
      </section>
    </>
  )
}
