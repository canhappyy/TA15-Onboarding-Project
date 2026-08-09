import type {
  ApiErrorCode,
  Route,
  RouteSearchRequest,
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

const apiErrorCodes: Record<ApiErrorCode, true> = {
  INVALID_REQUEST: true,
  OUTSIDE_SERVICE_AREA: true,
  NOT_FOUND: true,
  UPSTREAM_TIMEOUT: true,
  UPSTREAM_ERROR: true,
  DATA_UNAVAILABLE: true,
  TOO_MANY_REQUESTS: true,
  INTERNAL_SERVER_ERROR: true,
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null
}

function isApiErrorCode(value: unknown): value is ApiErrorCode {
  return typeof value === "string" && Object.hasOwn(apiErrorCodes, value)
}

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

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw invalidResponse()
  }

  if (!isRecord(payload) || typeof payload.success !== "boolean") {
    throw invalidResponse()
  }

  if (!payload.success) {
    if (
      !isRecord(payload.error) ||
      !isApiErrorCode(payload.error.code) ||
      typeof payload.error.message !== "string"
    ) {
      throw invalidResponse()
    }
    throw new RouteSearchApiError(payload.error.code, payload.error.message)
  }

  if (!response.ok || !isRecord(payload.data) || !Array.isArray(payload.data.routes)) {
    throw invalidResponse()
  }

  return payload.data.routes as Route[]
}
