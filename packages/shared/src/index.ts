export type ApiErrorCode =
  | "INVALID_REQUEST"
  | "OUTSIDE_SERVICE_AREA"
  | "NOT_FOUND"
  | "UPSTREAM_TIMEOUT"
  | "UPSTREAM_ERROR"
  | "DATA_UNAVAILABLE"
  | "TOO_MANY_REQUESTS"
  | "INTERNAL_SERVER_ERROR"

export type ApiSuccess<T> = {
  success: true
  data: T
}

export type ApiFailure = {
  success: false
  error: {
    code: ApiErrorCode
    message: string
  }
}

export type ApiResponse<T> = ApiSuccess<T> | ApiFailure

export type SensoryIndicator = "LOW" | "HIGH"

export type Coordinates = {
  latitude: number
  longitude: number
}

export type GeoJsonLineString = {
  type: "LineString"
  coordinates: [longitude: number, latitude: number][]
}

export type DataFreshness = {
  observedAt: string | null
  stale: boolean
  fallbackUsed: boolean
}

export type LocationSuggestion = {
  id: string
  label: string
  coordinates: Coordinates
}

export type LocationSearchData = {
  suggestions: LocationSuggestion[]
}

export type Route = {
  id: string
  durationMinutes: number
  walkingDistanceKm: number
  score: number
  indicator: SensoryIndicator
  geometry: GeoJsonLineString
  recommended: boolean
  warning: string | null
  explanation: string
  freshness: DataFreshness
}

export type RouteSearchRequest = {
  origin: Coordinates
  destination: Coordinates
}

export type RouteSearchData = {
  routes: Route[]
}

export type RefugeCategory = "LIBRARY" | "MUSEUM" | "GARDEN" | "PARK"

export type Refuge = {
  id: string
  name: string
  category: RefugeCategory
  coordinates: Coordinates
  walkingDistanceKm: number
  metadata: Record<string, string>
  navigationUrl: string
}

export type RefugeSearchRequest = {
  origin: Coordinates
  route: GeoJsonLineString
  categories?: RefugeCategory[]
}

export type RefugeSearchData = {
  refuges: Refuge[]
}

export type CongestionSensor = {
  id: string
  name: string
  indicator: SensoryIndicator
  pedestrianCount: number | null
  coordinates: Coordinates
  freshness: DataFreshness
}

export type CongestionData = {
  sensors: CongestionSensor[]
  freshness: DataFreshness
  staleWarning: string | null
}

export type LocationSearchResponse = ApiResponse<LocationSearchData>
export type RouteSearchResponse = ApiResponse<RouteSearchData>
export type RefugeSearchResponse = ApiResponse<RefugeSearchData>
export type CongestionResponse = ApiResponse<CongestionData>
