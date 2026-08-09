import type {
  ApiErrorCode,
  Refuge,
  RefugeListRequest,
} from "@clearway/shared"

import { parseRefugeResponse } from "@/lib/refuge-response"

export type RefugeListErrorCode =
  | ApiErrorCode
  | "CONFIGURATION_ERROR"
  | "MALFORMED_RESPONSE"
  | "NETWORK_ERROR"

export class RefugeListApiError extends Error {
  constructor(
    readonly code: RefugeListErrorCode,
    message: string
  ) {
    super(message)
    this.name = "RefugeListApiError"
  }
}

export async function listRefuges(
  request: RefugeListRequest,
  options?: { signal?: AbortSignal }
): Promise<Refuge[]> {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "")
  if (!apiBaseUrl) {
    throw new RefugeListApiError(
      "CONFIGURATION_ERROR",
      "Quiet spaces are not configured."
    )
  }

  const query = new URLSearchParams({
    latitude: String(request.latitude),
    longitude: String(request.longitude),
  })
  if (request.category) {
    query.set("category", request.category)
  }

  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}/refuges?${query}`, {
      headers: { Accept: "application/json" },
      signal: options?.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error
    }
    throw new RefugeListApiError(
      "NETWORK_ERROR",
      "Quiet spaces are unavailable. Try again."
    )
  }

  return parseRefugeResponse(
    response,
    (code, message) => new RefugeListApiError(code, message),
    "Quiet spaces returned an invalid response."
  )
}
