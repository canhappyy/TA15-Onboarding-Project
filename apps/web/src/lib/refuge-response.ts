import type { ApiErrorCode, Refuge } from "@clearway/shared"

export type RefugeResponseErrorCode = ApiErrorCode | "MALFORMED_RESPONSE"

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

const refugeCategories = new Set(["LIBRARY", "MUSEUM", "GARDEN", "PARK"])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null
}

function isApiErrorCode(value: unknown): value is ApiErrorCode {
  return typeof value === "string" && Object.hasOwn(apiErrorCodes, value)
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value)
}

function isSafeNavigationUrl(value: unknown): value is string {
  if (typeof value !== "string") return false

  try {
    return new URL(value).protocol === "https:"
  } catch {
    return false
  }
}

function isRefuge(value: unknown): value is Refuge {
  if (!isRecord(value) || !isRecord(value.coordinates) || !isRecord(value.metadata)) {
    return false
  }

  const { latitude, longitude } = value.coordinates
  const metadataValues = Object.values(value.metadata)

  return (
    typeof value.id === "string" &&
    value.id.trim().length > 0 &&
    typeof value.name === "string" &&
    value.name.trim().length > 0 &&
    typeof value.category === "string" &&
    refugeCategories.has(value.category) &&
    isFiniteNumber(latitude) &&
    latitude >= -90 &&
    latitude <= 90 &&
    isFiniteNumber(longitude) &&
    longitude >= -180 &&
    longitude <= 180 &&
    isFiniteNumber(value.walkingDistanceKm) &&
    value.walkingDistanceKm >= 0 &&
    value.metadata.source === "City of Melbourne Open Data" &&
    metadataValues.every((metadataValue) => typeof metadataValue === "string") &&
    isSafeNavigationUrl(value.navigationUrl)
  )
}

export async function parseRefugeResponse(
  response: Response,
  createError: (code: RefugeResponseErrorCode, message: string) => Error,
  malformedMessage: string
): Promise<Refuge[]> {
  const invalidResponse = () => createError("MALFORMED_RESPONSE", malformedMessage)

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
    throw createError(payload.error.code, payload.error.message)
  }

  if (
    !response.ok ||
    !isRecord(payload.data) ||
    !Array.isArray(payload.data.refuges) ||
    !payload.data.refuges.every(isRefuge)
  ) {
    throw invalidResponse()
  }

  return payload.data.refuges
}
