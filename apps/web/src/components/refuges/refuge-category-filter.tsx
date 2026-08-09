import type { RefugeFilter } from "@/lib/refuge-filter"

interface RefugeCategoryFilterProps {
  activeFilter: RefugeFilter
  onToggleFilter: (filter: RefugeFilter) => void
  className?: string
}

const filters: { label: string; value: RefugeFilter }[] = [
  { label: "All", value: "all" },
  { label: "Park", value: "PARK" },
  { label: "Garden", value: "GARDEN" },
  { label: "Library", value: "LIBRARY" },
  { label: "Museum", value: "MUSEUM" },
]

export function RefugeCategoryFilter({
  activeFilter,
  onToggleFilter,
  className = "",
}: RefugeCategoryFilterProps) {
  return (
    <section className={`flex items-center gap-2.5 overflow-x-auto pb-1 no-scrollbar ${className}`}>
      {filters.map((filter) => {
        const isSelected = activeFilter === filter.value
        return (
          <button
            key={filter.value}
            type="button"
            onClick={() => onToggleFilter(filter.value)}
            aria-pressed={isSelected}
            className={`cursor-pointer rounded-lg px-4 py-1.5 text-xs font-bold transition-all duration-200 ${
              isSelected
                ? "bg-[#475569] text-white shadow-xs scale-102"
                : "bg-[#8da2cf]/70 text-white/95 hover:bg-[#8da2cf]"
            }`}
          >
            {filter.label}
          </button>
        )
      })}
    </section>
  )
}
