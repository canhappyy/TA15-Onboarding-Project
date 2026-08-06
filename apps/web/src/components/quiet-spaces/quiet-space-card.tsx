import Link from "next/link"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  ChevronRightIcon,
  Tree01Icon,
  Coffee01Icon,
  Book02Icon,
} from "@hugeicons/core-free-icons"
import { type QuietSpace } from "@/lib/mock-quiet-spaces"
import { Card } from "@/components/ui/card"

const CATEGORY_ICONS = {
  Park: Tree01Icon,
  Cafe: Coffee01Icon,
  Library: Book02Icon,
}

interface QuietSpaceCardProps {
  space: QuietSpace
  href?: string
}

export function QuietSpaceCard({ space, href = "/quiet-spaces" }: QuietSpaceCardProps) {
  const Icon = CATEGORY_ICONS[space.category]

  return (
    <Link
      href={href}
      className="group block w-full active:scale-[0.99] transition-all duration-200"
    >
      <Card className="flex flex-row items-center justify-between border border-slate-100/80 bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] ring-0 transition-colors duration-200 group-hover:bg-slate-50/80 dark:border-slate-800/80 dark:bg-slate-900 dark:group-hover:bg-slate-800/80">
        <div className="flex items-center gap-3.5">
          <span className="flex size-11 items-center justify-center rounded-xl bg-slate-50 text-slate-500 transition-colors group-hover:bg-slate-100 group-hover:text-slate-700 dark:bg-slate-800 dark:text-slate-400 dark:group-hover:bg-slate-700 dark:group-hover:text-slate-300">
            <HugeiconsIcon icon={Icon} size={20} strokeWidth={2} />
          </span>
          <div className="flex flex-col gap-0.5">
            <div className="text-[15px] font-semibold text-slate-800 dark:text-white">
              {space.name}
            </div>
            <div className="text-xs font-medium text-slate-400 dark:text-slate-500">
              {space.category} · {space.distance}
            </div>
          </div>
        </div>

        <HugeiconsIcon
          icon={ChevronRightIcon}
          size={18}
          className="text-slate-400 transition-transform duration-200 group-hover:translate-x-0.5 dark:text-slate-500"
        />
      </Card>
    </Link>
  )
}
