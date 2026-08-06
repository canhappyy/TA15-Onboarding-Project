"use client"

import { Map } from "@/components/map/map"
import { useQuietSpaces } from "@/hooks/use-quiet-spaces"
import { QuietSpaceFilterComponent } from "@/components/quiet-spaces/quiet-space-filter"
import { QuietSpaceCard } from "@/components/quiet-spaces/quiet-space-card"
import { AppLogo } from "@/components/shared/app-logo"

export default function QuietSpacesPage() {
  const { activeFilter, filteredQuietSpaces, toggleFilter } = useQuietSpaces()

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
        activeFilter={activeFilter}
        onToggleFilter={toggleFilter}
      />

      {/* Map Area */}
      <div className="relative h-72 w-full overflow-hidden rounded-3xl border border-slate-100/80 bg-white shadow-[0_8px_30px_rgb(0,0,0,0.02)] dark:border-slate-800/80 dark:bg-slate-900">
        <Map />
      </div>

      {/* List of quiet spaces */}
      <section className="flex flex-col gap-3">
        <div className="flex flex-col gap-3">
          {filteredQuietSpaces.map((space) => (
            <QuietSpaceCard key={space.id} space={space} />
          ))}
        </div>
      </section>
    </div>
  )
}
