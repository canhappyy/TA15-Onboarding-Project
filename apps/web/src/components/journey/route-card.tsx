import type { Route } from "@clearway/shared"

interface RouteCardProps {
  route: Route
}

export function RouteCard({ route }: RouteCardProps) {
  const indicatorClass = route.indicator === "LOW"
    ? "bg-[#8da2cf] text-white"
    : "bg-[#ef4444] text-white"

  return (
    <article className="flex flex-col gap-3 rounded-2xl border border-slate-100/80 bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] dark:border-slate-800/80 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-3">
        <div className="flex gap-1 text-[15px] font-semibold text-slate-800 dark:text-white">
          <span>{route.durationMinutes} min</span>
          <span aria-hidden="true">·</span>
          <span>{route.walkingDistanceKm} km</span>
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
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
        {route.explanation}
      </p>
      {route.warning && (
        <p className="text-xs font-medium text-red-700 dark:text-red-300">
          {route.warning}
        </p>
      )}
    </article>
  )
}
