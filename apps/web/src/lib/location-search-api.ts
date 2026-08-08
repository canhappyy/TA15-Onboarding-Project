import type {
  ApiErrorCode,
  LocationSearchResponse,
  LocationSuggestion,
} from "@clearway/shared"

export type LocationSearchErrorCode =
  | ApiErrorCode
  | "CONFIGURATION_ERROR"
  | "NETWORK_ERROR"

export class LocationSearchApiError extends Error {
  constructor(
    readonly code: LocationSearchErrorCode,
    message: string
  ) {
    super(message)
    this.name = "LocationSearchApiError"
  }
}

type SearchOptions = {
  signal?: AbortSignal
}

export async function searchLocations(
  text: string,
  { signal }: SearchOptions = {}
): Promise<LocationSuggestion[]> {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "")
  if (!apiBaseUrl) {
    throw new LocationSearchApiError(
      "CONFIGURATION_ERROR",
      "Location search is not configured."
    )
  }

  let response: Response
  try {
    response = await fetch(
      `${apiBaseUrl}/locations/search?${new URLSearchParams({ text })}`,
      {
        headers: { Accept: "application/json" },
        signal,
      }
    )
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error
    }
    throw new LocationSearchApiError(
      "NETWORK_ERROR",
      "Location search is unavailable. Try again."
    )
  }

  let payload: LocationSearchResponse
  try {
    payload = (await response.json()) as LocationSearchResponse
  } catch {
    throw new LocationSearchApiError(
      "UPSTREAM_ERROR",
      "Location search returned an invalid response."
    )
  }

  if (!payload || typeof payload !== "object" || typeof payload.success !== "boolean") {
    throw new LocationSearchApiError(
      "UPSTREAM_ERROR",
      "Location search returned an invalid response."
    )
  }

  if (!payload.success) {
    throw new LocationSearchApiError(payload.error.code, payload.error.message)
  }

  if (!response.ok || !payload.data || !Array.isArray(payload.data.suggestions)) {
    throw new LocationSearchApiError(
      "UPSTREAM_ERROR",
      "Location search returned an invalid response."
    )
  }

  return payload.data.suggestions
}
