import Link from "next/link"
import { HugeiconsIcon } from "@hugeicons/react"
import { ChevronRightIcon } from "@hugeicons/core-free-icons"
import { type Route } from "@/lib/mock-routes"

interface RouteCardProps {
  route: Route
  href?: string
}

export function RouteCard({ route, href = "/journey/results" }: RouteCardProps) {
  return (
    <Link
      href={href}
      className="group flex items-center justify-between rounded-2xl border border-slate-100/80 bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition-all duration-200 hover:bg-slate-50/80 active:scale-[0.99] dark:border-slate-800/80 dark:bg-slate-900"
    >
      <div className="flex flex-col gap-1">
        <div className="text-[15px] font-semibold text-slate-800 dark:text-white">
          {route.time} • {route.distance}
        </div>
        <div className="text-xs font-medium text-slate-400 dark:text-slate-500">
          {route.via}
        </div>
      </div>

      <div className="flex flex-col items-end justify-between self-stretch min-h-[44px]">
        <span
          className={`rounded-md px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${route.badgeClass}`}
        >
          {route.crowdLevel}
        </span>
        <HugeiconsIcon
          icon={ChevronRightIcon}
          size={18}
          className="text-slate-400 transition-transform duration-200 group-hover:translate-x-0.5 dark:text-slate-500"
        />
      </div>
    </Link>
  )
}
