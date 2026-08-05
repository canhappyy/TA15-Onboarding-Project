import { Map } from "@/components/map/map"

export default function HomePage() {
  return (
    <main className="p-4">
      <div className="h-80 overflow-hidden rounded-3xl border">
        <Map />
      </div>
    </main>
  )
}