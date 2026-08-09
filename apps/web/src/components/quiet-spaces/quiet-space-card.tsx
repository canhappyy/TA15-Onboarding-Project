import { HugeiconsIcon } from "@hugeicons/react"
import {
  Tree01Icon,
  Book02Icon,
} from "@hugeicons/core-free-icons"
import type { Refuge, RefugeCategory } from "@clearway/shared"
import { Card } from "@/components/ui/card"

const CATEGORY_ICONS: Record<RefugeCategory, typeof Tree01Icon> = {
  PARK: Tree01Icon,
  GARDEN: Tree01Icon,
  LIBRARY: Book02Icon,
  MUSEUM: Book02Icon,
}

interface QuietSpaceCardProps {
  refuge: Refuge
}

export function QuietSpaceCard({ refuge }: QuietSpaceCardProps) {
  const Icon = CATEGORY_ICONS[refuge.category]

  return (
    <Card className="flex flex-row items-center justify-between border border-slate-100/80 bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] ring-0 transition-colors duration-200 dark:border-slate-800/80 dark:bg-slate-900">
      <article className="flex min-w-0 flex-1 items-center gap-3.5" aria-label={refuge.name}>
        <div className="flex items-center gap-3.5">
          <span className="flex size-11 items-center justify-center rounded-xl bg-slate-50 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            <HugeiconsIcon icon={Icon} size={20} strokeWidth={2} />
          </span>
          <div className="flex flex-col gap-0.5">
            <div className="text-[15px] font-semibold text-slate-800 dark:text-white">
              {refuge.name}
            </div>
            <div className="text-xs font-medium text-slate-400 dark:text-slate-500">
              {refuge.category} · {refuge.walkingDistanceKm.toFixed(1)} km away
            </div>
            <div className="text-xs text-slate-400 dark:text-slate-500">
              {refuge.metadata.source}
            </div>
          </div>
        </div>
      </article>
      <a
        href={refuge.navigationUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="ml-3 rounded-lg bg-slate-100 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
        aria-label={`Navigate to ${refuge.name}`}
      >
        Navigate
      </a>
    </Card>
  )
}
