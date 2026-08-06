import Link from "next/link"
import Image from "next/image"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowLeft02Icon } from "@hugeicons/core-free-icons"

interface JourneyHeaderProps {
  backHref?: string
  className?: string
}

export function JourneyHeader({ backHref = "/", className = "" }: JourneyHeaderProps) {
  return (
    <header className={`relative flex items-center justify-center py-2.5 ${className}`}>
      <Link
        href={backHref}
        className="absolute left-0 flex size-9 items-center justify-center rounded-xl text-slate-500 hover:text-slate-800 transition-colors dark:text-slate-400 dark:hover:text-white"
        aria-label="Back to previous page"
      >
        <HugeiconsIcon icon={ArrowLeft02Icon} size={20} strokeWidth={2.5} />
      </Link>
      <Image
        src="/clearway-logo.png"
        alt="Clearway Logo"
        width={130}
        height={32}
        className="h-8 w-auto opacity-85 dark:invert"
      />
    </header>
  )
}
