import React from "react"
import { Input } from "@/components/ui/input"

interface JourneyInputProps extends React.ComponentPropsWithoutRef<typeof Input> {
  icon: React.ReactNode
}

export function JourneyInput({ icon, className, ...props }: JourneyInputProps) {
  return (
    <div className="flex w-full items-center gap-3.5 rounded-2xl border border-slate-100 bg-white px-5 py-2.5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition-all duration-200 focus-within:border-slate-300 focus-within:ring-3 focus-within:ring-slate-100 dark:border-slate-800 dark:bg-slate-900 dark:focus-within:border-slate-700 dark:focus-within:ring-slate-800">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
        {icon}
      </span>
      <Input
        className={`h-auto border-none bg-transparent p-0 text-sm font-medium tracking-tight text-slate-700 outline-none ring-0 placeholder:text-slate-400/80 focus:outline-none focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 dark:text-slate-200 ${className || ""}`}
        {...props}
      />
    </div>
  )
}
