import { Button } from "@/components/ui/button"
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react"
import { ChevronRightIcon } from "@hugeicons/core-free-icons"
import React from "react"

interface NavButtonProps extends React.ComponentPropsWithoutRef<typeof Button> {
  icon: IconSvgElement
  label: string
}

export function NavButton({ icon, label, className, ...props }: NavButtonProps) {
  return (
    <Button
      variant="outline"
      className={`group flex h-auto w-full items-center justify-between rounded-2xl border border-slate-100 bg-white px-5 py-4 text-left text-slate-700 shadow-xs transition-all duration-200 hover:bg-slate-50/80 hover:text-slate-900 active:scale-[0.99] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800/80 dark:hover:text-white ${className || ""}`}
      {...props}
    >
      <span className="flex items-center gap-3.5">
        <span className="flex size-9 items-center justify-center rounded-xl bg-slate-50 text-slate-500 transition-colors group-hover:bg-slate-100 group-hover:text-slate-700 dark:bg-slate-800 dark:text-slate-400 dark:group-hover:bg-slate-700 dark:group-hover:text-slate-300">
          <HugeiconsIcon icon={icon} size={18} strokeWidth={2} />
        </span>
        <span className="text-sm font-medium tracking-tight">
          {label}
        </span>
      </span>
      <HugeiconsIcon
        icon={ChevronRightIcon}
        size={18}
        className="text-slate-400 transition-transform duration-200 group-hover:translate-x-0.5 dark:text-slate-500"
      />
    </Button>
  )
}
