import type { RouteFilter } from "@/hooks/use-journey"

interface JourneyFilterProps {
  activeFilter: RouteFilter
  onToggleFilter: (filter: "LOW" | "HIGH") => void
  className?: string
}

export function JourneyFilter({
  activeFilter,
  onToggleFilter,
  className = "",
}: JourneyFilterProps) {
  return (
    <section className={`flex items-center gap-3 text-xs font-semibold text-slate-500 dark:text-slate-400 ${className}`}>
      <span>Filter crowd level:</span>
      <button
        type="button"
        onClick={() => onToggleFilter("LOW")}
        className={`cursor-pointer rounded-md px-3 py-1 font-bold transition-all duration-200 ${
          activeFilter === "LOW"
            ? "bg-[#8da2cf] text-white shadow-xs scale-105"
            : "bg-[#8da2cf]/15 text-[#8da2cf] hover:bg-[#8da2cf]/25"
        }`}
      >
        Low
      </button>
      <button
        type="button"
        onClick={() => onToggleFilter("HIGH")}
        className={`cursor-pointer rounded-md px-3 py-1 font-bold transition-all duration-200 ${
          activeFilter === "HIGH"
            ? "bg-[#ef4444] text-white shadow-xs scale-105"
            : "bg-[#ef4444]/15 text-[#ef4444] hover:bg-[#ef4444]/25"
        }`}
      >
        High
      </button>
    </section>
  )
}
