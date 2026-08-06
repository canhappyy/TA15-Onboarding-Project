import { AppLogo } from "@/components/shared/app-logo"
import { NavButton } from "@/components/shared/nav-button"
import { Search02Icon, Yoga01Icon } from "@hugeicons/core-free-icons"

export default function JourneyPage() {
  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-3 animate-fade-in">
      {/* App Header / Logo */}
      <AppLogo />

      {/* Action Navigation Buttons */}
      <nav className="flex flex-col gap-3">
        <NavButton
          icon={Search02Icon}
          label="Where would you like to go?"
        />

        <NavButton
          icon={Yoga01Icon}
          label="Find a quiet space"
        />
      </nav>
    </div>
  )
}