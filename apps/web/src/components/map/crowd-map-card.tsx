import { Map } from "@/components/map/map"

interface CrowdMapCardProps {
  className?: string
  lastUpdated?: string
}

export function CrowdMapCard({ className, lastUpdated = "10:30 PM" }: CrowdMapCardProps) {
  return (
    <section className={`flex flex-col rounded-3xl border border-slate-100/80 bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] dark:border-slate-800/80 dark:bg-slate-900 ${className || ""}`}>
      <h2 className="mb-3 text-base font-semibold tracking-tight text-slate-700 dark:text-slate-300">
        Current Crowds
      </h2>
      
      {/* Map & Legend container */}
      <div className="flex h-72 items-stretch gap-4">
        {/* Map Area */}
        <div className="relative flex-1 overflow-hidden rounded-2xl border border-slate-100 dark:border-slate-800">
          <Map />
        </div>

        {/* Vertical Legend */}
        <div className="flex flex-col items-center justify-between py-1 text-slate-400">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
            High
          </span>
          <div className="my-1.5 w-2.5 flex-1 rounded-full bg-gradient-to-t from-blue-400 via-orange-400 to-rose-500 shadow-inner" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
            Low
          </span>
        </div>
      </div>

      <p className="mt-3 text-[11px] font-medium text-slate-400 dark:text-slate-500">
        Last Updated: {lastUpdated}
      </p>
    </section>
  )
}
