import Image from "next/image"

interface AppLogoProps {
  className?: string
}

export function AppLogo({ className }: AppLogoProps) {
  return (
    <header className={`flex flex-col items-center justify-center py-4 text-center ${className || ""}`}>
      <Image
        src="/clearway-logo.png"
        alt="Clearway Logo Placeholder"
        width={130}
        height={32}
        priority
        className="h-8 w-auto opacity-85 dark:invert"
      />
      <p className="mt-2 text-sm font-semibold tracking-wide text-slate-500 dark:text-slate-400">
        Sensory Friendly Way-finding
      </p>
    </header>
  )
}
