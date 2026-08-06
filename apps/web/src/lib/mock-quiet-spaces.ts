export interface QuietSpace {
  id: string
  name: string
  category: "Park" | "Library" | "Cafe"
  distance: string
}

export const MOCK_QUIET_SPACES: QuietSpace[] = [
  {
    id: "qs-1",
    name: "Carlton Gardens",
    category: "Park",
    distance: "0.3km",
  },
  {
    id: "qs-2",
    name: "City Café",
    category: "Cafe",
    distance: "0.8km",
  },
  {
    id: "qs-3",
    name: "State Library",
    category: "Library",
    distance: "1km",
  },
]
