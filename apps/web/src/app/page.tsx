import { AppLogo } from "@/components/shared/app-logo"
import { NavButton } from "@/components/shared/nav-button"
import { CrowdMapCard } from "@/components/map/crowd-map-card"
import { Search02Icon, Yoga01Icon } from "@hugeicons/core-free-icons"

export default function HomePage() {
  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-3 animate-fade-in">
      {/* App Header / Logo */}
      <AppLogo />

      {/* Map Card */}
      <CrowdMapCard />

      {/* Action Navigation Buttons */}
      <nav className="flex flex-col gap-3">
        <NavButton
          icon={Search02Icon}
          label="Where would you like to go?"
          href="/journey"
        />

        <NavButton
          icon={Yoga01Icon}
          label="Find a quiet space"
        />
      </nav>
    </div>
  )
}