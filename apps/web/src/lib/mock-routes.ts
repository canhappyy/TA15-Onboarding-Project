export interface Route {
  id: string
  time: string
  distance: string
  via: string
  crowdLevel: "Low" | "Medium" | "High"
  badgeClass: string
}

export const MOCK_ROUTES: Route[] = [
  {
    id: "route-1",
    time: "12 min",
    distance: "0.9km",
    via: "Via Collins St",
    crowdLevel: "Low",
    badgeClass: "bg-[#8da2cf] text-white",
  },
  {
    id: "route-2",
    time: "10 min",
    distance: "0.85km",
    via: "Via Elizabeth St",
    crowdLevel: "Medium",
    badgeClass: "bg-[#f0a030] text-white",
  },
  {
    id: "route-3",
    time: "9 min",
    distance: "0.7km",
    via: "Via Swanston St",
    crowdLevel: "High",
    badgeClass: "bg-[#ef4444] text-white",
  },
]
