import type {
  ApiErrorCode,
  Refuge,
  RefugeSearchRequest,
} from "@clearway/shared"

import { parseRefugeResponse } from "@/lib/refuge-response"

export type JourneyRefugeSearchErrorCode =
  | ApiErrorCode
  | "CONFIGURATION_ERROR"
  | "MALFORMED_RESPONSE"
  | "NETWORK_ERROR"

export class JourneyRefugeSearchApiError extends Error {
  constructor(
    readonly code: JourneyRefugeSearchErrorCode,
    message: string
  ) {
    super(message)
    this.name = "JourneyRefugeSearchApiError"
  }
}

export async function searchJourneyRefuges(
  request: RefugeSearchRequest,
  options?: { signal?: AbortSignal }
): Promise<Refuge[]> {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "")
  if (!apiBaseUrl) {
    throw new JourneyRefugeSearchApiError(
      "CONFIGURATION_ERROR",
      "Journey quiet spaces are not configured."
    )
  }

  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}/refuges/search`, {
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
    throw new JourneyRefugeSearchApiError(
      "NETWORK_ERROR",
      "Journey quiet spaces are unavailable. Try again."
    )
  }

  return parseRefugeResponse(
    response,
    (code, message) => new JourneyRefugeSearchApiError(code, message),
    "Journey quiet spaces returned an invalid response."
  )
}
