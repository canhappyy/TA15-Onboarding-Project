"use client"

import { Map } from "@/components/map/map"
import { useQuietSpaces } from "@/hooks/use-quiet-spaces"
import { QuietSpaceFilterComponent } from "@/components/quiet-spaces/quiet-space-filter"
import { QuietSpaceCard } from "@/components/quiet-spaces/quiet-space-card"
import { AppLogo } from "@/components/shared/app-logo"

export default function QuietSpacesPage() {
  const quietSpaces = useQuietSpaces()
  const filteredCount = quietSpaces.filteredRefuges.length

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-3 animate-fade-in">
      {/* App Header / Logo */}
      <AppLogo />

      {/* Page Title */}
      <h1 className="text-[17px] font-semibold tracking-tight text-slate-800 dark:text-slate-100">
        Quiet spaces near you
      </h1>

      {/* Category filters */}
      <QuietSpaceFilterComponent
        activeFilter={quietSpaces.activeFilter}
        onToggleFilter={quietSpaces.toggleFilter}
      />

      {/* Map Area */}
      <div className="relative h-72 w-full overflow-hidden rounded-3xl border border-slate-100/80 bg-white shadow-[0_8px_30px_rgb(0,0,0,0.02)] dark:border-slate-800/80 dark:bg-slate-900">
        <Map origin={quietSpaces.origin} refuges={quietSpaces.filteredRefuges} />
      </div>

      {/* List of quiet spaces */}
      <section className="flex flex-col gap-3">
        {quietSpaces.locationStatus === "locating" ? (
          <p role="status" aria-live="polite">Locating your position…</p>
        ) : null}
        {quietSpaces.locationStatus === "denied" ? (
          <div role="alert" className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100">
            <p>{quietSpaces.geolocationError ?? "We could not access your location."}</p>
            <button type="button" onClick={() => void quietSpaces.useFallbackOrigin()} className="mt-3 rounded-lg bg-amber-900 px-3 py-2 text-xs font-bold text-white dark:bg-amber-100 dark:text-amber-950">
              Use Melbourne CBD
            </button>
          </div>
        ) : null}
        {quietSpaces.usingFallback && quietSpaces.locationStatus === "ready" ? (
          <p role="status" aria-live="polite">Using Melbourne CBD as your location.</p>
        ) : null}
        {quietSpaces.loading ? (
          <p role="status" aria-live="polite">Searching quiet spaces…</p>
        ) : null}
        {quietSpaces.error ? (
          <div role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-900 dark:bg-red-950 dark:text-red-100">
            <p>{quietSpaces.error}</p>
            <button type="button" onClick={() => void quietSpaces.retrySearch()} className="mt-3 rounded-lg bg-red-900 px-3 py-2 text-xs font-bold text-white dark:bg-red-100 dark:text-red-950">
              Retry
            </button>
          </div>
        ) : null}
        {quietSpaces.hasSearched && !quietSpaces.loading && !quietSpaces.error && filteredCount === 0 ? (
          <p role="status" aria-live="polite">
            {quietSpaces.refuges.length === 0
              ? "No quiet spaces found near you."
              : `No quiet spaces match ${quietSpaces.activeFilter === "all" ? "this filter" : quietSpaces.activeFilter[0] + quietSpaces.activeFilter.slice(1).toLowerCase()}.`}
          </p>
        ) : null}
        {quietSpaces.hasSearched && !quietSpaces.loading && !quietSpaces.error && filteredCount > 0 ? (
          <>
            <p role="status" aria-live="polite">{filteredCount} quiet {filteredCount === 1 ? "space" : "spaces"} found</p>
            <div className="flex flex-col gap-3">
              {quietSpaces.filteredRefuges.map((refuge) => (
                <QuietSpaceCard key={refuge.id} refuge={refuge} />
              ))}
            </div>
          </>
        ) : null}
      </section>
    </div>
  )
}
