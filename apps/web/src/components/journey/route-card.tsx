import type { Route } from "@clearway/shared"

interface RouteCardProps {
  route: Route
  selected: boolean
  onSelect: (routeId: string) => void
}

export function RouteCard({ route, selected, onSelect }: RouteCardProps) {
  const indicatorClass = route.indicator === "LOW"
    ? "bg-[#8da2cf] text-white"
    : "bg-[#ef4444] text-white"
  const dataStatus = route.freshness.stale
    ? "Pedestrian data may be stale"
    : route.freshness.fallbackUsed
      ? "Historical pedestrian data used"
      : "Live pedestrian data"

  return (
    <article
      className={`flex flex-col gap-3 rounded-2xl border bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition dark:bg-slate-900 ${
        selected
          ? "border-[#475569] ring-2 ring-[#8da2cf]/40 dark:border-[#8da2cf]"
          : "border-slate-100/80 dark:border-slate-800/80"
      }`}
    >
      <button
        type="button"
        onClick={() => onSelect(route.id)}
        aria-label={`${selected ? "Selected" : "Select"} ${route.durationMinutes} minute ${route.indicator} sensory route`}
        aria-pressed={selected}
        aria-expanded={selected}
        className="cursor-pointer text-left"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1 text-[15px] font-semibold text-slate-800 dark:text-white">
            <span>{route.durationMinutes} min</span>
            <span aria-hidden="true">·</span>
            <span>{route.walkingDistanceKm} km</span>
            {selected && (
              <span className="ml-1 text-[10px] font-bold uppercase tracking-wider text-[#475569] dark:text-[#8da2cf]">
                Selected route
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {route.recommended && (
              <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                Recommended
              </span>
            )}
            <span className={`rounded-md px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${indicatorClass}`}>
              {route.indicator}
            </span>
          </div>
        </div>
      </button>
      {route.warning && (
        <p className="text-xs font-medium text-red-700 dark:text-red-300">
          {route.warning}
        </p>
      )}
      {selected && (
        <div className="flex flex-col gap-2 border-t border-slate-100 pt-3 text-xs text-slate-600 dark:border-slate-800 dark:text-slate-300">
          <p className="font-semibold text-slate-800 dark:text-slate-100">
            Sensory score {route.score}
          </p>
          <p>Data status: {dataStatus}</p>
          <details>
            <summary className="cursor-pointer font-semibold text-[#475569] dark:text-[#8da2cf]">
              How is this sensory score calculated?
            </summary>
            <p className="mt-2">{route.explanation}</p>
          </details>
        </div>
      )}
    </article>
  )
}
