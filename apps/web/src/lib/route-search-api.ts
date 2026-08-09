import type {
  ApiErrorCode,
  Route,
  RouteSearchRequest,
  RouteSearchResponse,
} from "@clearway/shared"

export type RouteSearchErrorCode =
  | ApiErrorCode
  | "CONFIGURATION_ERROR"
  | "NETWORK_ERROR"

export class RouteSearchApiError extends Error {
  constructor(
    readonly code: RouteSearchErrorCode,
    message: string
  ) {
    super(message)
    this.name = "RouteSearchApiError"
  }
}

const invalidResponse = () =>
  new RouteSearchApiError(
    "UPSTREAM_ERROR",
    "Route search returned an invalid response."
  )

export async function searchRoutes(
  request: RouteSearchRequest,
  options?: { signal?: AbortSignal }
): Promise<Route[]> {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "")
  if (!apiBaseUrl) {
    throw new RouteSearchApiError(
      "CONFIGURATION_ERROR",
      "Route search is not configured."
    )
  }

  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}/routes/search`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
      signal: options?.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error
    }
    throw new RouteSearchApiError(
      "NETWORK_ERROR",
      "Route search is unavailable. Try again."
    )
  }

  let payload: RouteSearchResponse
  try {
    payload = (await response.json()) as RouteSearchResponse
  } catch {
    throw invalidResponse()
  }

  if (!payload || typeof payload !== "object" || typeof payload.success !== "boolean") {
    throw invalidResponse()
  }

  if (!payload.success) {
    if (
      !payload.error ||
      typeof payload.error.code !== "string" ||
      typeof payload.error.message !== "string"
    ) {
      throw invalidResponse()
    }
    throw new RouteSearchApiError(payload.error.code, payload.error.message)
  }

  if (!response.ok || !payload.data || !Array.isArray(payload.data.routes)) {
    throw invalidResponse()
  }

  return payload.data.routes
}
