import type { Refuge } from "@clearway/shared"

import { RefugeCategoryFilter } from "@/components/refuges/refuge-category-filter"
import { Button } from "@/components/ui/button"
import type { RefugeFilter } from "@/lib/refuge-filter"

type JourneyRefugeControlsProps = {
  refuges: Refuge[]
  filteredRefuges: Refuge[]
  activeFilter: RefugeFilter
  loading: boolean
  error: string | null
  hasSearched: boolean
  onToggleFilter: (filter: RefugeFilter) => void
  onRetry: () => void
}

export function JourneyRefugeControls({
  refuges,
  filteredRefuges,
  activeFilter,
  loading,
  error,
  hasSearched,
  onToggleFilter,
  onRetry,
}: JourneyRefugeControlsProps) {
  const count = activeFilter === "all" ? refuges.length : filteredRefuges.length
  const category = activeFilter.charAt(0) + activeFilter.slice(1).toLowerCase()

  return (
    <section
      role="region"
      aria-label="Quiet spaces along this route"
      className="flex flex-col gap-2"
    >
      <RefugeCategoryFilter
        activeFilter={activeFilter}
        onToggleFilter={onToggleFilter}
      />
      {loading ? (
        <p role="status" aria-live="polite" className="text-sm text-slate-500 dark:text-slate-400">
          Finding quiet spaces…
        </p>
      ) : error ? (
        <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          <span>{error}</span>
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : hasSearched && activeFilter !== "all" && count === 0 ? (
        <p role="status" className="text-sm text-slate-500 dark:text-slate-400">
          No quiet spaces match {category}.
        </p>
      ) : hasSearched ? (
        <p role="status" className="text-sm text-slate-500 dark:text-slate-400">
          {count} quiet space{count !== 1 && "s"} found
        </p>
      ) : null}
    </section>
  )
}
