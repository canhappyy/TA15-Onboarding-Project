interface JourneyFilterProps {
  activeFilter: "all" | "Low" | "High"
  onToggleFilter: (filter: "Low" | "High") => void
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
        onClick={() => onToggleFilter("Low")}
        className={`cursor-pointer rounded-md px-3 py-1 font-bold transition-all duration-200 ${
          activeFilter === "Low"
            ? "bg-[#8da2cf] text-white shadow-xs scale-105"
            : "bg-[#8da2cf]/15 text-[#8da2cf] hover:bg-[#8da2cf]/25"
        }`}
      >
        Low
      </button>
      <button
        type="button"
        onClick={() => onToggleFilter("High")}
        className={`cursor-pointer rounded-md px-3 py-1 font-bold transition-all duration-200 ${
          activeFilter === "High"
            ? "bg-[#f0a030] text-white shadow-xs scale-105"
            : "bg-[#f0a030]/15 text-[#f0a030] hover:bg-[#f0a030]/25"
        }`}
      >
        High
      </button>
    </section>
  )
}
